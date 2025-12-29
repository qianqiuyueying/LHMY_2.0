"""属性测试：核销成功才扣次数（属性15）。

规格来源：
- specs/health-services-platform/design.md -> 属性 15：核销成功才扣次数
- specs/health-services-platform/tasks.md -> 阶段5-31.5
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.models.enums import EntitlementType
from app.services.entitlement_redeem_rules import apply_redeem


@given(
    entitlement_type=st.sampled_from([EntitlementType.SERVICE_PACKAGE.value]),
    remaining=st.integers(min_value=0, max_value=20),
)
def test_property_15_only_success_changes_remaining(entitlement_type: str, remaining: int):
    before = remaining
    after_fail = apply_redeem(entitlement_type=entitlement_type, remaining_count=remaining, success=False)
    assert after_fail.remaining_count == before

    after_success = apply_redeem(entitlement_type=entitlement_type, remaining_count=remaining, success=True)
    assert after_success.remaining_count == max(0, before - 1)
