"""可售服务卡（SellableCard）配置（v2.1）。

规格来源：
- specs/health-services-platform/dealer-link-sellable-cards-v1.md（v2.1：可售卡自带售价；去掉计价商品依赖）
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CommonEnabledStatus
from app.utils.datetime_utc import utcnow


class SellableCard(Base):
    __tablename__ = "sellable_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="可售卡ID（sellableCardId）")

    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="展示名（例如：健身市卡-北京）")

    # v2.1：不再依赖“计价商品（Product）”，保留该字段仅为兼容历史数据
    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="（v2.1 废弃）计价商品ID")
    service_package_template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="服务包模板ID")

    # v2：只配置“区域级别”；具体区域由消费者购买时选择并写入订单明细（OrderItem.region_scope）
    # 取值口径与区域编码规则一致：CITY/PROVINCE/COUNTRY
    region_level: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="CITY",
        comment="卡片区域级别：CITY/PROVINCE/COUNTRY",
    )

    # v1 字段（保留兼容历史数据；v2 不再写入/读取）
    region_scope: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="（v1 废弃）区域范围（例如 CITY:110100）")
    tier: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="（v1 废弃）等级覆盖（可选）")

    # v2.1：唯一售价（订单计价依据）
    price_original: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="可售卡唯一售价（元，v2.1）",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CommonEnabledStatus.ENABLED.value,
        comment="状态：ENABLED/DISABLED",
    )
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序（越大越靠前）")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow, comment="更新时间"
    )

