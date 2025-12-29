"""结算记录模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> SettlementRecord
- specs/health-services-platform/tasks.md -> 阶段2-10.4
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import SettlementStatus


class SettlementRecord(Base):
    __tablename__ = "settlement_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="结算单号")

    dealer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="经销商ID")

    cycle: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="结算周期标识")

    order_count: Mapped[int] = mapped_column(nullable=False, default=0, comment="订单数")

    amount: Mapped[float] = mapped_column(nullable=False, default=0.0, comment="应结算金额")

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SettlementStatus.PENDING_CONFIRM.value,
        comment="状态：PENDING_CONFIRM/SETTLED/FROZEN",
    )

    payout_method: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="打款方式快照：BANK/ALIPAY")
    payout_account_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="打款账户快照（JSON）")
    payout_reference: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="打款流水号/参考号")
    payout_note: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="打款备注")
    payout_marked_by: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="标记打款的管理员ID")
    payout_marked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="标记打款时间")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结算完成时间")
