"""Admin 核销记录查询接口（v1 最小可执行）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-004
- specs/health-services-platform/design.md -> RedemptionRecord 模型

接口：
- GET /api/v1/admin/redemptions
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.v1.deps import require_admin
from app.models.redemption_record import RedemptionRecord
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["admin-redemptions"])


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


def _dto(r: RedemptionRecord) -> dict:
    return {
        "id": r.id,
        "entitlementId": r.entitlement_id,
        "bookingId": r.booking_id,
        "userId": r.user_id,
        "venueId": r.venue_id,
        "serviceType": r.service_type,
        "operatorId": r.operator_id,
        "status": r.status,
        "failureReason": r.failure_reason,
        "redemptionTime": r.redemption_time.astimezone().isoformat(),
    }


@router.get("/admin/redemptions")
async def admin_list_redemptions(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    dateFrom: str | None = None,
    dateTo: str | None = None,
    serviceType: str | None = None,
    status: str | None = None,
    operatorId: str | None = None,
    userId: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(RedemptionRecord)

    if dateFrom:
        stmt = stmt.where(RedemptionRecord.redemption_time >= _parse_dt_utc_naive(dateFrom, field_name="dateFrom"))
    if dateTo:
        # dateTo 允许 YYYY-MM-DD：按当日 23:59:59 处理
        if len(dateTo) == 10:
            dt = _parse_dt_utc_naive(dateTo + "T23:59:59", field_name="dateTo")
        else:
            dt = _parse_dt_utc_naive(dateTo, field_name="dateTo")
        stmt = stmt.where(RedemptionRecord.redemption_time <= dt)

    if serviceType and serviceType.strip():
        stmt = stmt.where(RedemptionRecord.service_type == serviceType.strip())
    if status and status.strip():
        stmt = stmt.where(RedemptionRecord.status == status.strip())
    if operatorId and operatorId.strip():
        stmt = stmt.where(RedemptionRecord.operator_id == operatorId.strip())
    if userId and userId.strip():
        stmt = stmt.where(RedemptionRecord.user_id == userId.strip())

    stmt = stmt.order_by(RedemptionRecord.redemption_time.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )
