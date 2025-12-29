"""属性测试：预约确认机制正确性（属性17）。

规格来源：
- specs/health-services-platform/design.md -> 属性 17：预约确认机制正确性
- specs/health-services-platform/design.md -> bookings.status 迁移（AUTO/MANUAL）
- specs/health-services-platform/tasks.md -> 阶段6-37.5
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.enums import BookingConfirmationMethod, BookingStatus
from app.services.booking_confirmation_rules import booking_state_on_create


def test_property_17_auto_confirmation_creates_confirmed_booking():
    now = datetime.now(tz=UTC)
    state = booking_state_on_create(confirmation_method=BookingConfirmationMethod.AUTO.value, now=now)
    assert state.confirmation_method == BookingConfirmationMethod.AUTO.value
    assert state.status == BookingStatus.CONFIRMED.value
    assert state.confirmed_at == now


def test_property_17_manual_confirmation_creates_pending_booking():
    now = datetime.now(tz=UTC)
    state = booking_state_on_create(confirmation_method=BookingConfirmationMethod.MANUAL.value, now=now)
    assert state.confirmation_method == BookingConfirmationMethod.MANUAL.value
    assert state.status == BookingStatus.PENDING.value
    assert state.confirmed_at is None
