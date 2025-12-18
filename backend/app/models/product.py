"""商品模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> 商品模型（interface Product）
- specs/health-services-platform/tasks.md -> 阶段2-6.1

说明：
- v1：不支持实物商品；只允许 VIRTUAL_VOUCHER / SERVICE。
- price 作为 JSON 存储，便于保持与契约结构一致。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ProductFulfillmentType, ProductStatus


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="商品ID")
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="服务提供方ID")

    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="标题")
    fulfillment_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProductFulfillmentType.SERVICE.value,
        comment="履约类型：VIRTUAL_VOUCHER/SERVICE",
    )

    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="分类ID")

    cover_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="封面图")
    image_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="图片列表")

    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="描述（富文本/文本）")

    # 价格字段用于“属性12：价格优先级”裁决；为空表示该价格不可用
    price: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="价格对象")

    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="标签")

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProductStatus.PENDING_REVIEW.value,
        comment="状态：PENDING_REVIEW/ON_SALE/OFF_SHELF/REJECTED",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
