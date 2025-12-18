"""场所排期配置模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> VenueSchedule
- specs/health-services-platform/tasks.md -> 阶段2-9.3

说明：
- bookingDate + timeSlot 为最小可执行口径。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CommonEnabledStatus


class VenueSchedule(Base):
    __tablename__ = "venue_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="排期ID")

    venue_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="场所ID")

    service_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="服务类目标识")

    booking_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="预约日期")

    time_slot: Mapped[str] = mapped_column(String(16), nullable=False, comment="时段：HH:mm-HH:mm")

    capacity: Mapped[int] = mapped_column(nullable=False, default=0, comment="总容量")
    remaining_capacity: Mapped[int] = mapped_column(nullable=False, default=0, comment="剩余容量")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CommonEnabledStatus.ENABLED.value,
        comment="状态：ENABLED/DISABLED",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
