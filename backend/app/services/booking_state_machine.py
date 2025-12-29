"""预约状态机（REQ-P1-006）。

规格来源：
- specs/health-services-platform/后端升级需求与变更清单（v1）.md -> REQ-P1-006
- specs/health-services-platform/design.md -> 预约状态（PENDING/CONFIRMED/CANCELLED/COMPLETED）
"""

from __future__ import annotations

from fastapi import HTTPException

from app.models.enums import BookingStatus


_ALLOWED: dict[str, set[str]] = {
    BookingStatus.PENDING.value: {BookingStatus.CONFIRMED.value, BookingStatus.CANCELLED.value},
    BookingStatus.CONFIRMED.value: {BookingStatus.COMPLETED.value, BookingStatus.CANCELLED.value},
    BookingStatus.CANCELLED.value: set(),
    BookingStatus.COMPLETED.value: set(),
}


def assert_booking_status_transition(*, current: str, target: str) -> None:
    allowed = _ALLOWED.get(str(current), set())
    if str(target) not in allowed:
        raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "预约状态不允许变更"})

