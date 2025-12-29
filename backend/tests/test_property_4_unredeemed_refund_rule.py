"""属性测试：未核销退款规则（属性4）。

规格来源：
- specs/health-services-platform/design.md -> 属性 4：未核销退款规则
- specs/health-services-platform/tasks.md -> 阶段8-48.4（Property 4）

v1 最小断言：
- 对于任意“未发生 SUCCESS 核销”的权益集合，退款规则应允许；
- 一旦存在任意 SUCCESS 核销，退款规则应拒绝（错误码 REFUND_NOT_ALLOWED）。
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.refund_rules import can_refund_unredeemed_entitlements


@given(redeemed_success_count=st.integers(min_value=0, max_value=10_000))
def test_property_4_unredeemed_refund_rule(redeemed_success_count: int):
    res = can_refund_unredeemed_entitlements(redeemed_success_count=redeemed_success_count)
    if redeemed_success_count == 0:
        assert res.ok is True
        assert res.error_code is None
    else:
        assert res.ok is False
        assert res.error_code == "REFUND_NOT_ALLOWED"
