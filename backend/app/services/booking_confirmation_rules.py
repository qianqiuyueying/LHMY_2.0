"""预约确认规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> bookings.status 迁移（AUTO/MANUAL）
- specs/health-services-platform/design.md -> 属性 17：预约确认机制正确性
- specs/health-services-platform/tasks.md -> 阶段6-37.4 / 37.5

说明：
- 本模块只表达“给定确认模式时，预约应落到何种状态/字段”的纯规则。
- 确认模式的配置载体（SystemConfig / per-venue 等）在 API 层确定。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import BookingConfirmationMethod, BookingStatus


@dataclass(frozen=True)
class BookingCreatedState:
    status: str
    confirmation_method: str
    confirmed_at: datetime | None


def booking_state_on_create(*, confirmation_method: str, now: datetime) -> BookingCreatedState:
    """创建预约后应处于的状态（属性17）。"""

    if confirmation_method == BookingConfirmationMethod.AUTO.value:
        return BookingCreatedState(
            status=BookingStatus.CONFIRMED.value,
            confirmation_method=BookingConfirmationMethod.AUTO.value,
            confirmed_at=now,
        )

    # 默认 MANUAL：保持 PENDING，等待 PROVIDER/ADMIN 确认
    return BookingCreatedState(
        status=BookingStatus.PENDING.value,
        confirmation_method=BookingConfirmationMethod.MANUAL.value,
        confirmed_at=None,
    )

