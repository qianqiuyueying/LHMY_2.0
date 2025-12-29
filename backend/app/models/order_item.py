"""订单明细模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> 订单明细模型（interface OrderItem）
- specs/health-services-platform/tasks.md -> 阶段2-7.2
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import OrderItemType


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="明细ID")
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
        comment="订单ID",
    )

    # 对应业务对象：商品/服务包模板
    item_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OrderItemType.PRODUCT.value,
        comment="明细类型：PRODUCT/SERVICE_PACKAGE",
    )

    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="业务对象ID")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="标题")

    quantity: Mapped[int] = mapped_column(nullable=False, default=1, comment="数量")
    unit_price: Mapped[float] = mapped_column(nullable=False, default=0.0, comment="单价")
    unit_price_type: Mapped[str] = mapped_column(String(16), nullable=False, default="original", comment="单价来源：activity/member/employee/original")
    total_price: Mapped[float] = mapped_column(nullable=False, default=0.0, comment="总价")

    # 健行天下（高端服务卡）购买参数（仅当 itemType=SERVICE_PACKAGE 时适用）
    service_package_template_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="服务包模板ID（service_packages）",
    )
    region_scope: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="区域范围（见区域编码口径）")
    tier: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="等级/阶梯")
