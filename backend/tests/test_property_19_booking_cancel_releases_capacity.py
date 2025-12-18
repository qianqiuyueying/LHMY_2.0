"""属性测试：预约取消状态恢复（属性19）。

规格来源：
- specs/health-services-platform/design.md -> 属性 19：预约取消状态恢复
- specs/health-services-platform/tasks.md -> 阶段6-39.4

v1 最小断言：
- 取消预约应释放预约容量（remainingCapacity 回升）
- 取消预约不应扣减用户服务次数（v1：取消不触发 entitlement remainingCount 变化；该点在 API 侧通过“不写 entitlement”保证）
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.booking_capacity_rules import release_capacity


@given(
    capacity=st.integers(min_value=0, max_value=500),
    remaining=st.integers(min_value=0, max_value=500),
)
def test_property_19_release_capacity_never_exceeds_capacity(capacity: int, remaining: int):
    new_remaining = release_capacity(remaining_capacity=remaining, capacity=capacity)
    assert 0 <= new_remaining <= max(0, capacity)
    # 至少回升 1（除非已满或容量为 0）
    if capacity > 0 and remaining < capacity:
        assert new_remaining == remaining + 1
    else:
        assert new_remaining == max(0, min(capacity, remaining))

