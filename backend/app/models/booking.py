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
from app.models.enums import BookingConfirmationMethod, BookingSourceType, BookingStatus
from app.utils.datetime_utc import utcnow


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="预约ID")

    source_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=BookingSourceType.ENTITLEMENT.value,
        comment="来源：ENTITLEMENT/ORDER_ITEM",
    )

    # v1：权益预约；vNow：允许为空（当 sourceType=ORDER_ITEM 时）
    entitlement_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="权益ID")
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="订单ID（ORDER_ITEM 预约）")
    order_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="订单明细ID（ORDER_ITEM 预约）")
    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="商品ID（ORDER_ITEM 预约）")
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

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
