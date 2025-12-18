"""核销规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 权益（entitlements.status）与扣次数规则
- specs/health-services-platform/design.md -> 属性 15：核销成功才扣次数
- specs/health-services-platform/tasks.md -> 阶段5-31.3/31.5

口径（v1）：
- 仅当核销成功时才扣次数/作废
- 次数权益（SERVICE_PACKAGE）：remainingCount 递减；remainingCount==0 时置为 USED
- 虚拟券（VOUCHER）：核销成功直接置为 USED（remainingCount 可置 0）
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import EntitlementStatus, EntitlementType


@dataclass(frozen=True)
class RedeemResult:
    remaining_count: int
    status: str


def apply_redeem(
    *,
    entitlement_type: str,
    remaining_count: int,
    success: bool,
) -> RedeemResult:
    """根据核销结果更新权益次数与状态（纯函数）。"""

    remaining_count = int(remaining_count)
    if not success:
        return RedeemResult(remaining_count=remaining_count, status=EntitlementStatus.ACTIVE.value)

    if entitlement_type == EntitlementType.VOUCHER.value:
        return RedeemResult(remaining_count=0, status=EntitlementStatus.USED.value)

    if entitlement_type == EntitlementType.SERVICE_PACKAGE.value:
        new_remaining = max(0, remaining_count - 1)
        new_status = EntitlementStatus.USED.value if new_remaining == 0 else EntitlementStatus.ACTIVE.value
        return RedeemResult(remaining_count=new_remaining, status=new_status)

    # 未知类型：保守不改
    return RedeemResult(remaining_count=remaining_count, status=EntitlementStatus.ACTIVE.value)

