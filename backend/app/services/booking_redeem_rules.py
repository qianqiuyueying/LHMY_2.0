"""预约与核销关联规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 属性 16：预约与核销关联性
- specs/health-services-platform/design.md -> 核销规则：需要预约的服务必须已确认预约
- specs/health-services-platform/tasks.md -> 阶段5-31.4/31.6
"""

from __future__ import annotations


def can_redeem_with_booking_requirement(*, booking_required: bool, has_confirmed_booking: bool) -> bool:
    """若服务需要预约，则必须存在已确认预约才允许核销。"""

    if not booking_required:
        return True
    return bool(has_confirmed_booking)
