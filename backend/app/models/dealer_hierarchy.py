"""经销商层级关系（闭包表，v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> DealerHierarchy
- specs/health-services-platform/tasks.md -> 阶段2-10.2

说明：
- depth：ancestor==descendant 为 0；直接下级为 1。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.datetime_utc import utcnow


class DealerHierarchy(Base):
    __tablename__ = "dealer_hierarchies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="关系ID")

    ancestor_dealer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="祖先经销商ID")
    descendant_dealer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="后代经销商ID")

    depth: Mapped[int] = mapped_column(nullable=False, default=0, comment="深度")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
