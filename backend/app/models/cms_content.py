"""CMS 内容模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> CmsContent
- specs/health-services-platform/tasks.md -> 阶段2-11.2

说明：
- v1：以富文本 HTML 为最小承载。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CmsContentStatus


class CmsContent(Base):
    __tablename__ = "cms_contents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="内容ID")

    channel_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="栏目ID")

    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="标题")
    cover_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="封面图")
    summary: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="摘要")

    content_html: Mapped[str] = mapped_column(Text, nullable=False, comment="正文（HTML）")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CmsContentStatus.DRAFT.value,
        comment="状态：DRAFT/PUBLISHED/OFFLINE",
    )

    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发布时间")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效开始")
    effective_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效结束")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
