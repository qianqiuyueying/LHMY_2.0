"""订单主表模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> 订单支付模型（interface Order）
- specs/health-services-platform/tasks.md -> 阶段2-7.1
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import JSON
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
        comment="订单类型：PRODUCT/SERVICE_PACKAGE",
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
    dealer_link_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True, comment="投放链接ID（dealerLinkId）"
    )

    # 物流商品 v2：履约与收货信息（仅当 fulfillmentType=PHYSICAL_GOODS 时适用）
    fulfillment_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="履约类型：SERVICE/PHYSICAL_GOODS")
    fulfillment_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="物流状态：NOT_SHIPPED/SHIPPED/DELIVERED/RECEIVED（仅物流商品）",
    )
    goods_amount: Mapped[float] = mapped_column(nullable=False, default=0.0, comment="商品金额（不含运费）")
    shipping_amount: Mapped[float] = mapped_column(nullable=False, default=0.0, comment="运费金额")
    shipping_address_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="收货地址快照（JSON）")
    reservation_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="库存占用到期时间")

    shipping_carrier: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="快递公司")
    shipping_tracking_no: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="运单号")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发货时间")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="妥投时间")
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="确认收货时间")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="支付时间")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="银行转账确认时间")
