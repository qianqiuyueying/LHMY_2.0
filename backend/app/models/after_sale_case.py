"""售后申请模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 售后/退款（AfterSaleCase/Refund）
- specs/health-services-platform/tasks.md -> 阶段2-7.5
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AfterSaleDecision, AfterSaleStatus, AfterSaleType


class AfterSaleCase(Base):
    __tablename__ = "after_sale_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="申请单号")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="订单ID")
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="用户ID")

    type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AfterSaleType.REFUND.value,
        comment="类型：RETURN/REFUND/AFTER_SALE_SERVICE",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AfterSaleStatus.SUBMITTED.value,
        comment="状态：SUBMITTED/UNDER_REVIEW/DECIDED/CLOSED",
    )

    amount: Mapped[float] = mapped_column(nullable=False, default=0.0, comment="金额")

    reason: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="原因")
    evidence_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="举证URL列表")

    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="裁决人（adminId）")

    # v1：不支持部分退款/部分裁决（PARTIAL），仅允许全额通过或驳回
    decision: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="裁决：APPROVE/REJECT",
    )
    decision_notes: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="裁决备注")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
