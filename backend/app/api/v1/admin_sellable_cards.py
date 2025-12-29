"""Admin 可售卡（SellableCard）管理（v2.1）。

规格来源：
- specs/health-services-platform/dealer-link-sellable-cards-v1.md（v2.1）
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType
from app.models.enums import CommonEnabledStatus
from app.models.sellable_card import SellableCard
from app.models.service_package import ServicePackage
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso


router = APIRouter(tags=["admin-sellable-cards"])

def _dto(x: SellableCard) -> dict:
    return {
        "id": x.id,
        "name": x.name,
        "servicePackageTemplateId": x.service_package_template_id,
        "regionLevel": x.region_level,
        "priceOriginal": float(x.price_original or 0),
        "status": x.status,
        "sort": int(x.sort or 0),
        "createdAt": _iso(x.created_at),
        "updatedAt": _iso(x.updated_at),
    }

def _parse_upsert_body(body: Any) -> tuple[str, str, str, float, int]:
    """手动校验并收敛为 400 INVALID_ARGUMENT（避免 FastAPI 422 漂移）。"""

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})

    name = str(body.get("name") or "").strip()
    template_id = str(body.get("servicePackageTemplateId") or "").strip()
    region_level = str(body.get("regionLevel") or "").strip().upper()
    price_raw = body.get("priceOriginal")
    sort_raw = body.get("sort", 0)

    if not name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "name 不能为空"})
    if len(name) > 128:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "name 过长"})
    if not template_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "servicePackageTemplateId 不能为空"})
    if region_level not in {"CITY", "PROVINCE", "COUNTRY"}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "regionLevel 不合法"})
    if isinstance(price_raw, bool) or not isinstance(price_raw, (int, float)):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "priceOriginal 必须是数字"})
    price_original = float(price_raw)
    if price_original < 0:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "priceOriginal 不合法"})
    if isinstance(sort_raw, bool) or not isinstance(sort_raw, (int, float)):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "sort 必须是数字"})
    sort = int(sort_raw)

    return name, template_id, region_level, price_original, sort


@router.get("/admin/sellable-cards")
async def admin_list_sellable_cards(
    request: Request,
    page: int = 1,
    pageSize: int = 20,
    status: str | None = None,
    keyword: str | None = None,
    _admin=Depends(require_admin),
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))
    stmt = select(SellableCard)
    if status:
        st = str(status).strip().upper()
        if st not in {CommonEnabledStatus.ENABLED.value, CommonEnabledStatus.DISABLED.value}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})
        stmt = stmt.where(SellableCard.status == st)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(
            (SellableCard.id.like(kw))
            | (SellableCard.name.like(kw))
            | (SellableCard.service_package_template_id.like(kw))
            | (SellableCard.region_level.like(kw))
        )
    stmt = stmt.order_by(SellableCard.sort.desc(), SellableCard.updated_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(data={"items": [_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


async def _validate_refs(*, session, service_package_template_id: str, region_level: str) -> None:
    sp = (
        await session.scalars(select(ServicePackage).where(ServicePackage.id == service_package_template_id.strip()).limit(1))
    ).first()
    if sp is None:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "servicePackageTemplateId 不存在"})
    if str(sp.region_level).strip().upper() != str(region_level).strip().upper():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "regionLevel 与模板区域级别不一致"})


@router.post("/admin/sellable-cards")
async def admin_create_sellable_card(
    request: Request, body: dict[str, Any] = Body(default_factory=dict), admin=Depends(require_admin_phone_bound)
):
    admin_id = str(admin.sub)
    name, template_id, region_level, price_original, sort = _parse_upsert_body(body)
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _validate_refs(session=session, service_package_template_id=template_id, region_level=region_level)
        row = SellableCard(
            id=str(uuid4()),
            name=name,
            service_package_template_id=template_id,
            region_level=region_level,
            price_original=float(price_original),
            status=CommonEnabledStatus.ENABLED.value,
            sort=int(sort),
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
                resource_type="SELLABLE_CARD",
                resource_id=str(row.id),
                summary="ADMIN 新增可售卡",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "id": str(row.id),
                    "name": str(row.name),
                    "servicePackageTemplateId": str(row.service_package_template_id),
                    "regionLevel": str(row.region_level),
                    "priceOriginal": float(row.price_original or 0),
                    "sort": int(row.sort or 0),
                },
            )
        )

        await session.commit()
        await session.refresh(row)
    return ok(data=_dto(row), request_id=request.state.request_id)


@router.put("/admin/sellable-cards/{id}")
async def admin_update_sellable_card(
    request: Request,
    id: str,
    body: dict[str, Any] = Body(default_factory=dict),
    admin=Depends(require_admin_phone_bound),
):
    admin_id = str(admin.sub)
    name, template_id, region_level, price_original, sort = _parse_upsert_body(body)
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(SellableCard).where(SellableCard.id == id).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "可售卡不存在"})

        before = _dto(row)
        changed_fields: list[str] = []
        if name != str(row.name):
            changed_fields.append("name")
        if template_id != str(row.service_package_template_id):
            changed_fields.append("servicePackageTemplateId")
        if region_level != str(row.region_level).strip().upper():
            changed_fields.append("regionLevel")
        if float(price_original) != float(row.price_original or 0):
            changed_fields.append("priceOriginal")
        if int(sort) != int(row.sort or 0):
            changed_fields.append("sort")

        if not changed_fields:
            # no-op：不写审计
            return ok(data=_dto(row), request_id=request.state.request_id)

        await _validate_refs(session=session, service_package_template_id=template_id, region_level=region_level)
        row.name = name
        row.service_package_template_id = template_id
        row.region_level = region_level
        row.price_original = float(price_original)
        row.sort = int(sort)
        row.updated_at = datetime.now(tz=UTC).replace(tzinfo=None)

        after = _dto(row)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="SELLABLE_CARD",
                resource_id=str(row.id),
                summary="ADMIN 更新可售卡",
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


@router.post("/admin/sellable-cards/{id}/enable")
async def admin_enable_sellable_card(request: Request, id: str, admin=Depends(require_admin_phone_bound)):
    admin_id = str(admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(SellableCard).where(SellableCard.id == id).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "可售卡不存在"})
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
                resource_type="SELLABLE_CARD",
                resource_id=str(row.id),
                summary="ADMIN 启用可售卡",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "id": str(row.id),
                    "beforeStatus": before_status,
                    "afterStatus": str(row.status),
                },
            )
        )

        await session.commit()
        await session.refresh(row)
    return ok(data=_dto(row), request_id=request.state.request_id)


@router.post("/admin/sellable-cards/{id}/disable")
async def admin_disable_sellable_card(request: Request, id: str, admin=Depends(require_admin_phone_bound)):
    admin_id = str(admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(SellableCard).where(SellableCard.id == id).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "可售卡不存在"})
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
                resource_type="SELLABLE_CARD",
                resource_id=str(row.id),
                summary="ADMIN 停用可售卡",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "id": str(row.id),
                    "beforeStatus": before_status,
                    "afterStatus": str(row.status),
                },
            )
        )

        await session.commit()
        await session.refresh(row)
    return ok(data=_dto(row), request_id=request.state.request_id)

