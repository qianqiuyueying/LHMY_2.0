"""属性测试：预约与核销关联性（属性16）。

规格来源：
- specs/health-services-platform/design.md -> 属性 16：预约与核销关联性
- specs/health-services-platform/tasks.md -> 阶段5-31.6
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.booking_redeem_rules import can_redeem_with_booking_requirement


@given(
    booking_required=st.booleans(),
    has_confirmed_booking=st.booleans(),
)
def test_property_16_booking_required_gate(booking_required: bool, has_confirmed_booking: bool):
    ok = can_redeem_with_booking_requirement(
        booking_required=booking_required,
        has_confirmed_booking=has_confirmed_booking,
    )
    if booking_required:
        assert ok is has_confirmed_booking
    else:
        assert ok is True
