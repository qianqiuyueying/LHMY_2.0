"""场所服务模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> VenueService
- specs/health-services-platform/tasks.md -> 阶段2-9.2
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CommonEnabledStatus, ProductFulfillmentType, RedemptionMethod


class VenueService(Base):
    __tablename__ = "venue_services"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="场所服务ID")

    venue_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="场所ID")

    service_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="服务类目标识")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="展示标题")

    fulfillment_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProductFulfillmentType.SERVICE.value,
        comment="履约类型：SERVICE",
    )

    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="关联商品ID")

    booking_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否需要预约")

    redemption_method: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=RedemptionMethod.BOTH.value,
        comment="核销方式：QR_CODE/VOUCHER_CODE/BOTH（vNow：默认 BOTH）",
    )

    applicable_regions: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="适用区域标签")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CommonEnabledStatus.ENABLED.value,
        comment="状态：ENABLED/DISABLED",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
