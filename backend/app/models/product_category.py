"""商品分类（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> 商品分类（interface ProductCategory）
- specs/health-services-platform/tasks.md -> 阶段2-6.2
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CommonEnabledStatus
from app.utils.datetime_utc import utcnow


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="分类ID")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="分类名称")
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="父级ID")
    sort: Mapped[int] = mapped_column(nullable=False, default=0, comment="排序")
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CommonEnabledStatus.ENABLED.value,
        comment="状态：ENABLED/DISABLED",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
