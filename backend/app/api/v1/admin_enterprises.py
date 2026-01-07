"""Admin 企业信息库接口（v1 最小可执行）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-006
- specs/health-services-platform/prototypes/admin.md -> 企业信息库
- specs/health-services-platform/design.md -> enterprises 表与 EnterpriseSource 枚举

接口（v1 最小）：
- GET /api/v1/admin/enterprises
- GET /api/v1/admin/enterprises/{id}
 - PUT /api/v1/admin/enterprises/{id}（仅允许更新 name）

注意：
- PUT 的可编辑字段白名单已固化为“仅 name”（方案A从严），避免破坏历史绑定口径。
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.enterprise import Enterprise
from app.models.enums import AuditAction, AuditActorType, EnterpriseSource
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-enterprises"])


class AdminEnterpriseUpdateReq(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=256)


def _dto(e: Enterprise) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "countryCode": e.country_code,
        "provinceCode": e.province_code,
        "cityCode": e.city_code,
        "source": e.source,
        "firstSeenAt": _iso(e.first_seen_at),
        "createdAt": _iso(e.created_at),
        "updatedAt": _iso(e.updated_at),
    }


@router.get("/admin/enterprises")
async def admin_list_enterprises(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    keyword: str | None = None,
    cityCode: str | None = None,
    source: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Enterprise)

    if keyword and keyword.strip():
        stmt = stmt.where(Enterprise.name.like(f"%{keyword.strip()}%"))

    if cityCode and cityCode.strip():
        stmt = stmt.where(Enterprise.city_code == cityCode.strip())

    if source and source.strip():
        s = source.strip()
        if s not in {EnterpriseSource.USER_FIRST_BINDING.value, EnterpriseSource.IMPORT.value, EnterpriseSource.MANUAL.value}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "source 不合法"})
        stmt = stmt.where(Enterprise.source == s)

    stmt = stmt.order_by(Enterprise.first_seen_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.get("/admin/enterprises/{id}")
async def admin_get_enterprise(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin),
):
    _ = _admin

    session_factory = get_session_factory()
    async with session_factory() as session:
        e = (await session.scalars(select(Enterprise).where(Enterprise.id == id).limit(1))).first()

    if e is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "企业不存在"})

    return ok(data=_dto(e), request_id=request.state.request_id)


@router.put("/admin/enterprises/{id}")
async def admin_update_enterprise(
    request: Request,
    id: str,
    body: AdminEnterpriseUpdateReq,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)

    session_factory = get_session_factory()
    async with session_factory() as session:
        e = (await session.scalars(select(Enterprise).where(Enterprise.id == id).limit(1))).first()
        if e is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "企业不存在"})

        # 方案A从严：仅允许更新 name，其它字段一律不允许（extra=forbid 已拦截）
        before_name = str(e.name or "")
        e.name = body.name
        e.updated_at = datetime.utcnow()

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="ENTERPRISE",
                resource_id=str(e.id),
                summary="ADMIN 更新企业名称",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "enterpriseId": str(e.id),
                    "beforeName": before_name,
                    "afterName": str(body.name),
                },
            )
        )

        await session.commit()

    return ok(data=_dto(e), request_id=request.state.request_id)
