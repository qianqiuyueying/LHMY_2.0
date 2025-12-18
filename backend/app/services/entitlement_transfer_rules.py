"""转赠条件规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 属性 8：服务包退款和转赠条件
- specs/health-services-platform/tasks.md -> 阶段5-32.2/32.4

口径（属性8）：
- 核销维度：同一张服务包实例下所有权益的核销记录中，status=SUCCESS 数量为 0
- 次数维度：同一张服务包实例下所有权益满足 remainingCount == totalCount
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntitlementCounts:
    remaining_count: int
    total_count: int


def can_transfer_service_package(*, entitlements: list[EntitlementCounts], success_redemption_count: int) -> bool:
    if success_redemption_count != 0:
        return False
    if not entitlements:
        return False
    return all(int(x.remaining_count) == int(x.total_count) for x in entitlements)

