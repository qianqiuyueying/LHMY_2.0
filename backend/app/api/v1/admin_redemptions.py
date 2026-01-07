"""Admin 核销记录查询接口（v1 最小可执行）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-004
- specs/health-services-platform/design.md -> RedemptionRecord 模型

接口：
- GET /api/v1/admin/redemptions
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.v1.deps import require_admin
from app.models.redemption_record import RedemptionRecord
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-redemptions"])


_TZ_BEIJING = timezone(timedelta(hours=8))


def _parse_beijing_day(raw: str, *, field_name: str) -> date:
    try:
        if len(raw) != 10:
            raise ValueError("expected YYYY-MM-DD")
        return date.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 格式不合法"}) from exc


def _beijing_day_range_to_utc_naive(d: date) -> tuple[datetime, datetime]:
    start_bj = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    next_day = d + timedelta(days=1)
    end_bj_exclusive = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    return (
        start_bj.astimezone(timezone.utc).replace(tzinfo=None),
        end_bj_exclusive.astimezone(timezone.utc).replace(tzinfo=None),
    )


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
        "redemptionTime": _iso(r.redemption_time),
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

    # Spec (Admin): dateFrom/dateTo are Beijing natural days (YYYY-MM-DD)
    if dateFrom:
        d_from = _parse_beijing_day(str(dateFrom), field_name="dateFrom")
        start_utc, _end_exclusive = _beijing_day_range_to_utc_naive(d_from)
        stmt = stmt.where(RedemptionRecord.redemption_time >= start_utc)
    if dateTo:
        d_to = _parse_beijing_day(str(dateTo), field_name="dateTo")
        _start_utc, end_exclusive = _beijing_day_range_to_utc_naive(d_to)
        stmt = stmt.where(RedemptionRecord.redemption_time < end_exclusive)

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
