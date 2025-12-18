"""预约模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> Booking
- specs/health-services-platform/tasks.md -> 阶段2-9.4

说明：
- bookingDate + timeSlot 为最小可执行存储口径；开始/结束时间由二者派生。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import BookingConfirmationMethod, BookingStatus


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="预约ID")

    entitlement_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="权益ID")
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="用户ID")

    venue_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="场所ID")
    service_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="服务类目标识")

    booking_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="预约日期")
    time_slot: Mapped[str] = mapped_column(String(16), nullable=False, comment="时段：HH:mm-HH:mm")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=BookingStatus.PENDING.value,
        comment="状态：PENDING/CONFIRMED/CANCELLED/COMPLETED",
    )

    confirmation_method: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=BookingConfirmationMethod.AUTO.value,
        comment="确认方式：AUTO/MANUAL",
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="确认时间")
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="取消时间")
    cancel_reason: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="取消原因")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
