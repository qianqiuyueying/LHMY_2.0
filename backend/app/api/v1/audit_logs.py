"""审计日志查询（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 审计日志（AuditLog）数据模型
- specs/health-services-platform/design.md -> E-5 全局审计日志查询（v1 最小契约）
- specs/health-services-platform/tasks.md -> 阶段10-59.2/59.3
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.v1.deps import require_admin
from app.models.audit_log import AuditLog
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["admin-audit-logs"])


_TZ_BEIJING = timezone(timedelta(hours=8))


def _iso_utc_z(dt: datetime) -> str:
    """Return ISO 8601 UTC string with 'Z' suffix, seconds precision."""
    if dt.tzinfo is None:
        aware = dt.replace(tzinfo=timezone.utc)
    else:
        aware = dt.astimezone(timezone.utc)
    # normalize to seconds precision for stable output
    return aware.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_beijing_day(raw: str, *, field_name: str) -> date:
    try:
        # Expect YYYY-MM-DD from admin date picker
        if len(raw) != 10:
            raise ValueError("expected YYYY-MM-DD")
        return date.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}
        ) from exc


def _beijing_day_range_to_utc_naive(d: date) -> tuple[datetime, datetime]:
    """Convert a Beijing natural day to [start, endExclusive) in naive UTC datetimes.

    Spec:
    - dateFrom/dateTo are YYYY-MM-DD and interpreted as Beijing (UTC+8) natural days.
    - DB stores UTC in naive DATETIME.
    """

    start_bj = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    next_day = d + timedelta(days=1)
    end_bj_exclusive = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    return (
        start_bj.astimezone(timezone.utc).replace(tzinfo=None),
        end_bj_exclusive.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _mask_sensitive(value: Any) -> Any:
    """v1：出参兜底脱敏（避免历史脏数据在 metadata 中泄露）。"""
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for k, v in value.items():
            lk = str(k).lower()
            if lk in {"password", "password_hash", "token", "authorization", "smscode", "sms_code"}:
                masked[k] = "***"
            elif lk in {"phone", "mobile"} and isinstance(v, str):
                s = v.strip()
                masked[k] = f"{s[:3]}****{s[-4:]}" if len(s) >= 7 else None
            else:
                masked[k] = _mask_sensitive(v)
        return masked
    if isinstance(value, list):
        return [_mask_sensitive(x) for x in value]
    return value


def _dto(x: AuditLog) -> dict[str, Any]:
    return {
        "id": x.id,
        "actorType": x.actor_type,
        "actorId": x.actor_id,
        "action": x.action,
        "resourceType": x.resource_type,
        "resourceId": x.resource_id,
        "summary": x.summary,
        "ip": x.ip,
        "userAgent": x.user_agent,
        "metadata": _mask_sensitive(x.metadata_json) if x.metadata_json else None,
        # Spec: output UTC ISO 8601 with Z
        "createdAt": _iso_utc_z(x.created_at),
    }


@router.get("/admin/audit-logs")
async def admin_list_audit_logs(
    request: Request,
    actorType: Literal["ADMIN", "USER", "DEALER", "PROVIDER", "PROVIDER_STAFF"] | None = None,
    actorId: str | None = None,
    action: Literal["CREATE", "UPDATE", "PUBLISH", "OFFLINE", "APPROVE", "REJECT", "LOGIN", "LOGOUT"] | None = None,
    resourceType: str | None = None,
    resourceId: str | None = None,
    keyword: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
    _admin=Depends(require_admin),
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(AuditLog)
    if actorType:
        stmt = stmt.where(AuditLog.actor_type == str(actorType))
    if actorId and actorId.strip():
        stmt = stmt.where(AuditLog.actor_id == actorId.strip())
    if action:
        stmt = stmt.where(AuditLog.action == str(action))
    if resourceType and resourceType.strip():
        stmt = stmt.where(AuditLog.resource_type == resourceType.strip())
    if resourceId and resourceId.strip():
        stmt = stmt.where(AuditLog.resource_id == resourceId.strip())
    if keyword and keyword.strip():
        stmt = stmt.where(AuditLog.summary.like(f"%{keyword.strip()}%"))
    # Spec: dateFrom/dateTo are Beijing natural days (YYYY-MM-DD)
    if dateFrom:
        d_from = _parse_beijing_day(str(dateFrom), field_name="dateFrom")
        start_utc_naive, _end_utc_naive_exclusive = _beijing_day_range_to_utc_naive(d_from)
        stmt = stmt.where(AuditLog.created_at >= start_utc_naive)
    if dateTo:
        d_to = _parse_beijing_day(str(dateTo), field_name="dateTo")
        # inclusive end-of-day in Beijing, implemented as next day start (exclusive)
        _start_utc_naive, end_utc_naive_exclusive = _beijing_day_range_to_utc_naive(d_to)
        stmt = stmt.where(AuditLog.created_at < end_utc_naive_exclusive)

    stmt = stmt.order_by(AuditLog.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        logs = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_dto(x) for x in logs], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )
