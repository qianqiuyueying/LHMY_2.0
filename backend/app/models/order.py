"""订单主表模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> 订单支付模型（interface Order）
- specs/health-services-platform/tasks.md -> 阶段2-7.1
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import OrderType, PaymentMethod, PaymentStatus


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="订单ID（v1：展示字段 orderNo=id）")

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="用户ID")

    order_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OrderType.PRODUCT.value,
        comment="订单类型：PRODUCT/VIRTUAL_VOUCHER/SERVICE_PACKAGE",
    )

    total_amount: Mapped[float] = mapped_column(nullable=False, default=0.0, comment="订单总金额")

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

    dealer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="经销商归属")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="支付时间")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="银行转账确认时间")
