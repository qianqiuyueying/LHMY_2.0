"""服务大类字典（serviceType）模型（v1 可运营）。

规格来源：
- specs/health-services-platform/service-category-management.md
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CommonEnabledStatus
from app.utils.datetime_utc import utcnow


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="服务大类ID")

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="serviceType code")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="中文展示名")

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

