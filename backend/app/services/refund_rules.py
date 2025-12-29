"""退款规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> B9 售后/退款（after_sales / refunds）
- specs/health-services-platform/design.md -> 属性 4：未核销退款规则
- specs/health-services-platform/tasks.md -> 阶段8-48.2/48.4

v1 最小规则（属性4）：
- 对于“未发生核销”的权益，应允许退款申请；反之拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefundRuleResult:
    ok: bool
    error_code: str | None = None


def can_refund_unredeemed_entitlements(*, redeemed_success_count: int) -> RefundRuleResult:
    """未核销退款规则（属性4）。

    说明：
    - redeemed_success_count 指该订单对应的 SUCCESS 核销记录数量
    """

    if int(redeemed_success_count) <= 0:
        return RefundRuleResult(ok=True, error_code=None)
    return RefundRuleResult(ok=False, error_code="REFUND_NOT_ALLOWED")
