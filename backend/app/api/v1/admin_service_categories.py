"""Admin 服务大类（serviceType 字典）管理（v1 可运营）。

规格来源：
- specs/health-services-platform/service-category-management.md
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import func, or_, select

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType
from app.models.enums import CommonEnabledStatus
from app.models.service_category import ServiceCategory
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso


router = APIRouter(tags=["admin-service-categories"])

_CODE_RE = re.compile(r"^[A-Z0-9_]{2,64}$")


def _dto(x: ServiceCategory) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "displayName": x.display_name,
        "status": x.status,
        "sort": int(x.sort or 0),
        "createdAt": _iso(x.created_at),
        "updatedAt": _iso(x.updated_at),
    }

def _parse_create_body(body: Any) -> tuple[str, str, int]:
    """手动校验并收敛为 400 INVALID_ARGUMENT（避免 FastAPI 422 漂移）。"""

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})
    code = str(body.get("code") or "").strip().upper()
    display_name = str(body.get("displayName") or "").strip()
    sort_raw = body.get("sort", 0)

    if not code:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "code 不能为空"})
    if not _CODE_RE.fullmatch(code):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "code 格式不合法"})
    if not display_name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "displayName 不能为空"})
    if isinstance(sort_raw, bool) or not isinstance(sort_raw, (int, float)):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "sort 必须是数字"})
    sort = int(sort_raw)
    return code, display_name, sort


def _parse_update_body(body: Any) -> tuple[str | None, int | None]:
    """手动校验并收敛为 400 INVALID_ARGUMENT（避免 FastAPI 422 漂移）。"""

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})

    display_name: str | None = None
    if "displayName" in body:
        raw = body.get("displayName")
        if raw is None:
            display_name = None
        elif not isinstance(raw, str):
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "displayName 必须是 string"})
        else:
            dn = raw.strip()
            if not dn:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "displayName 不能为空"})
            display_name = dn

    sort: int | None = None
    if "sort" in body:
        raw = body.get("sort")
        if raw is None:
            sort = None
        else:
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "sort 必须是数字"})
            sort = int(raw)

    return display_name, sort


@router.get("/admin/service-categories")
async def admin_list_service_categories(
    request: Request,
    keyword: str | None = None,
    status: str | None = None,
    page: int = 1,
    pageSize: int = 20,
    _admin=Depends(require_admin),
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(ServiceCategory)

    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        stmt = stmt.where(or_(ServiceCategory.code.like(like), ServiceCategory.display_name.like(like)))

    if status:
        st = str(status).strip().upper()
        if st not in {CommonEnabledStatus.ENABLED.value, CommonEnabledStatus.DISABLED.value}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})
        stmt = stmt.where(ServiceCategory.status == st)

    # v1：排序优先 sort desc，其次 updated_at desc
    stmt = stmt.order_by(ServiceCategory.sort.desc(), ServiceCategory.updated_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.post("/admin/service-categories")
async def admin_create_service_category(
    request: Request,
    body: dict[str, Any] = Body(default_factory=dict),
    admin=Depends(require_admin_phone_bound),
):
    admin_id = str(admin.sub)
    code, display_name, sort = _parse_create_body(body)

    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = (await session.scalars(select(ServiceCategory).where(ServiceCategory.code == code).limit(1))).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "code 已存在"})

        row = ServiceCategory(
            id=str(uuid4()),
            code=code,
            display_name=display_name,
            status=CommonEnabledStatus.ENABLED.value,
            sort=sort,
            created_at=datetime.now(tz=UTC).replace(tzinfo=None),
            updated_at=datetime.now(tz=UTC).replace(tzinfo=None),
        )
        session.add(row)

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.CREATE.value,
                resource_type="SERVICE_CATEGORY",
                resource_id=str(row.id),
                summary="ADMIN 新增服务大类",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "id": str(row.id),
                    "code": str(row.code),
                    "displayName": str(row.display_name),
                    "sort": int(row.sort or 0),
                },
            )
        )

        await session.commit()
        await session.refresh(row)

    return ok(data=_dto(row), request_id=request.state.request_id)


@router.put("/admin/service-categories/{id}")
async def admin_update_service_category(
    request: Request,
    id: str,
    body: dict[str, Any] = Body(default_factory=dict),
    admin=Depends(require_admin_phone_bound),
):
    admin_id = str(admin.sub)
    display_name, sort = _parse_update_body(body)
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(ServiceCategory).where(ServiceCategory.id == id).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "服务大类不存在"})

        before = _dto(row)
        changed_fields: list[str] = []
        if display_name is not None and display_name != str(row.display_name):
            row.display_name = display_name
            changed_fields.append("displayName")
        if sort is not None and int(sort) != int(row.sort or 0):
            row.sort = int(sort)
            changed_fields.append("sort")

        if not changed_fields:
            # no-op：不写审计
            return ok(data=_dto(row), request_id=request.state.request_id)

        row.updated_at = datetime.now(tz=UTC).replace(tzinfo=None)
        after = _dto(row)

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="SERVICE_CATEGORY",
                resource_id=str(row.id),
                summary="ADMIN 更新服务大类",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "id": str(row.id),
                    "changedFields": changed_fields,
                    "before": before,
                    "after": after,
                },
            )
        )

        await session.commit()
        await session.refresh(row)

    return ok(data=_dto(row), request_id=request.state.request_id)


@router.post("/admin/service-categories/{id}/enable")
async def admin_enable_service_category(request: Request, id: str, admin=Depends(require_admin_phone_bound)):
    admin_id = str(admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(ServiceCategory).where(ServiceCategory.id == id).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "服务大类不存在"})
        if row.status == CommonEnabledStatus.ENABLED.value:
            # no-op：不写审计
            return ok(data=_dto(row), request_id=request.state.request_id)

        before_status = str(row.status)
        row.status = CommonEnabledStatus.ENABLED.value
        row.updated_at = datetime.now(tz=UTC).replace(tzinfo=None)

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="SERVICE_CATEGORY",
                resource_id=str(row.id),
                summary="ADMIN 启用服务大类",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "id": str(row.id),
                    "code": str(row.code),
                    "beforeStatus": before_status,
                    "afterStatus": str(row.status),
                },
            )
        )

        await session.commit()
        await session.refresh(row)
    return ok(data=_dto(row), request_id=request.state.request_id)


@router.post("/admin/service-categories/{id}/disable")
async def admin_disable_service_category(request: Request, id: str, admin=Depends(require_admin_phone_bound)):
    admin_id = str(admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(ServiceCategory).where(ServiceCategory.id == id).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "服务大类不存在"})
        if row.status == CommonEnabledStatus.DISABLED.value:
            # no-op：不写审计
            return ok(data=_dto(row), request_id=request.state.request_id)

        before_status = str(row.status)
        row.status = CommonEnabledStatus.DISABLED.value
        row.updated_at = datetime.now(tz=UTC).replace(tzinfo=None)

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="SERVICE_CATEGORY",
                resource_id=str(row.id),
                summary="ADMIN 停用服务大类",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "id": str(row.id),
                    "code": str(row.code),
                    "beforeStatus": before_status,
                    "afterStatus": str(row.status),
                },
            )
        )

        await session.commit()
        await session.refresh(row)
    return ok(data=_dto(row), request_id=request.state.request_id)

