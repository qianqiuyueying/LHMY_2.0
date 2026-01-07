"""购物车模型（REQ-P1-001）。

规格来源：
- specs/health-services-platform/后端升级需求与变更清单（v1）.md -> REQ-P1-001

v1 最小口径：
- Cart：每个用户一个“当前购物车”
- CartItem：以 (cart_id, item_type, item_id) 唯一，避免同商品重复行
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.datetime_utc import utcnow


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="购物车ID")
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True, comment="用户ID")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    __table_args__ = (
        UniqueConstraint("cart_id", "item_type", "item_id", name="uq_cart_items_cart_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="购物车项ID")
    cart_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="购物车ID")

    item_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="类型：PRODUCT/SERVICE_PACKAGE")
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="商品/服务包等业务对象ID")
    quantity: Mapped[int] = mapped_column(nullable=False, default=1, comment="数量")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )

