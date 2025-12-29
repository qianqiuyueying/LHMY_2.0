"""属性测试：服务包退款和转赠条件（属性8）。

规格来源：
- specs/health-services-platform/design.md -> 属性 8：服务包退款和转赠条件
- specs/health-services-platform/tasks.md -> 阶段5-32.4

v1 最小断言：
- 当且仅当：
  - success_redemption_count == 0
  - 且同一服务包实例下所有权益 remainingCount == totalCount
  才允许退款/转赠。
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.entitlement_transfer_rules import EntitlementCounts, can_transfer_service_package


@given(
    entitlements=st.lists(
        st.tuples(st.integers(min_value=0, max_value=50), st.integers(min_value=0, max_value=50)),
        min_size=1,
        max_size=10,
    ),
    success_redemption_count=st.integers(min_value=0, max_value=20),
)
def test_property_8_service_package_transfer_condition(
    entitlements: list[tuple[int, int]], success_redemption_count: int
):
    counts = [EntitlementCounts(remaining_count=r, total_count=t) for (r, t) in entitlements]
    expected = (success_redemption_count == 0) and all(r == t for (r, t) in entitlements)
    assert (
        can_transfer_service_package(entitlements=counts, success_redemption_count=success_redemption_count) is expected
    )
