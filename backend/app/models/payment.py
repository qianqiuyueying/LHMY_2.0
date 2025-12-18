"""支付记录模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段2-7.3（已在任务文档内补充 v1 最小字段口径）

说明：
- design.md 当前仅列出 payments 表名，但未给出字段结构；为保证可落地，这里按最小字段实现。
- 后续若需要对接微信支付的更多字段（如 prepay_id、transaction_id 等），应先更新规格再扩展。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import PaymentMethod, PaymentStatus


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="支付记录ID")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="订单ID")

    payment_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PaymentMethod.WECHAT.value,
        comment="支付方式：WECHAT/ALIPAY/BANK_TRANSFER",
    )

    payment_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PaymentStatus.PENDING.value,
        comment="支付状态：PENDING/PAID/FAILED/REFUNDED",
    )

    amount: Mapped[float] = mapped_column(nullable=False, default=0.0, comment="支付金额")

    # 支付渠道返回的原始字段（最小口径：保留 JSON 便于排障与扩展）
    provider_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="渠道原始返回")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
