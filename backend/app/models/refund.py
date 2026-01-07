"""退款记录模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 售后/退款（Refund）
- specs/health-services-platform/tasks.md -> 阶段2-7.4
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import RefundStatus
from app.utils.datetime_utc import utcnow


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="退款ID")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="订单ID")

    amount: Mapped[float] = mapped_column(nullable=False, default=0.0, comment="退款金额")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=RefundStatus.REQUESTED.value,
        comment="状态：REQUESTED/APPROVED/REJECTED/PROCESSING/SUCCESS/FAILED",
    )

    reason: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="原因")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
