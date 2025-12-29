"""Admin 权益转赠记录查询接口（v1 最小可执行）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-005
- specs/health-services-platform/tasks.md -> 阶段2-8.3（EntitlementTransfer 最小字段）

接口：
- GET /api/v1/admin/entitlement-transfers
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.v1.deps import require_admin
from app.models.entitlement_transfer import EntitlementTransfer
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["admin-entitlement-transfers"])


def _parse_dt_utc_naive(raw: str, *, field_name: str) -> datetime:
    try:
        if len(raw) == 10:
            dt = datetime.fromisoformat(raw + "T00:00:00")
        else:
            dt = datetime.fromisoformat(raw)
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        return dt
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 格式不合法"}) from exc


def _dto(t: EntitlementTransfer) -> dict:
    return {
        "id": t.id,
        "entitlementId": t.entitlement_id,
        "fromOwnerId": t.from_owner_id,
        "toOwnerId": t.to_owner_id,
        "transferredAt": t.transferred_at.astimezone().isoformat(),
    }


@router.get("/admin/entitlement-transfers")
async def admin_list_entitlement_transfers(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    fromOwnerId: str | None = None,
    toOwnerId: str | None = None,
    entitlementId: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(EntitlementTransfer)

    if fromOwnerId and fromOwnerId.strip():
        stmt = stmt.where(EntitlementTransfer.from_owner_id == fromOwnerId.strip())
    if toOwnerId and toOwnerId.strip():
        stmt = stmt.where(EntitlementTransfer.to_owner_id == toOwnerId.strip())
    if entitlementId and entitlementId.strip():
        stmt = stmt.where(EntitlementTransfer.entitlement_id == entitlementId.strip())

    if dateFrom:
        stmt = stmt.where(EntitlementTransfer.transferred_at >= _parse_dt_utc_naive(dateFrom, field_name="dateFrom"))
    if dateTo:
        if len(dateTo) == 10:
            dt = _parse_dt_utc_naive(dateTo + "T23:59:59", field_name="dateTo")
        else:
            dt = _parse_dt_utc_naive(dateTo, field_name="dateTo")
        stmt = stmt.where(EntitlementTransfer.transferred_at <= dt)

    stmt = stmt.order_by(EntitlementTransfer.transferred_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )
