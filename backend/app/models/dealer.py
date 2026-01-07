"""经销商模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> Dealer
- specs/health-services-platform/tasks.md -> 阶段2-10.1
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import DealerStatus
from app.utils.datetime_utc import utcnow


class Dealer(Base):
    __tablename__ = "dealers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="经销商ID")

    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="经销商名称")

    level: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="层级标识")
    parent_dealer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="上级经销商ID")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=DealerStatus.ACTIVE.value,
        comment="状态：ACTIVE/SUSPENDED",
    )

    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="联系人")
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="联系电话")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
