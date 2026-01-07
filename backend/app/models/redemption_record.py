"""核销记录模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> RedemptionRecord
- specs/health-services-platform/tasks.md -> 阶段2-8.4
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import RedemptionMethod, RedemptionStatus
from app.utils.datetime_utc import utcnow


class RedemptionRecord(Base):
    __tablename__ = "redemption_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="核销记录ID")

    entitlement_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="权益ID")
    booking_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="预约ID")

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="用户ID")
    venue_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="场所ID")

    service_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="服务类目标识")

    redemption_method: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=RedemptionMethod.QR_CODE.value,
        comment="方式：QR_CODE/VOUCHER_CODE",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=RedemptionStatus.SUCCESS.value,
        comment="状态：SUCCESS/FAILED",
    )

    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="失败原因")

    operator_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="操作人ID")

    redemption_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, comment="核销时间"
    )
    service_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="服务完成时间")

    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="备注")
