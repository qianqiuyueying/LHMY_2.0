"""健康场所模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> Venue
- specs/health-services-platform/tasks.md -> 阶段2-9.1
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import VenuePublishStatus, VenueReviewStatus
from app.utils.datetime_utc import utcnow


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="场所ID")

    provider_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="服务提供方ID")

    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="场所名称")

    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="LOGO")
    cover_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="封面图")
    image_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="图片列表")

    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="简介")

    country_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True, comment="国家编码")
    province_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True, comment="省编码")
    city_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True, comment="市编码")

    address: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="地址")
    lat: Mapped[float | None] = mapped_column(nullable=True, comment="纬度")
    lng: Mapped[float | None] = mapped_column(nullable=True, comment="经度")

    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="联系电话")
    business_hours: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="营业时间")

    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="标签")

    publish_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=VenuePublishStatus.DRAFT.value,
        comment="发布状态：DRAFT/PUBLISHED/OFFLINE",
    )

    review_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=VenueReviewStatus.DRAFT.value,
        comment="展示资料审核状态：DRAFT/SUBMITTED/APPROVED/REJECTED",
    )
    reject_reason: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="驳回原因（覆盖式）")
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="驳回时间")
    offline_reason: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="下线原因（覆盖式）")
    offlined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="下线时间")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
