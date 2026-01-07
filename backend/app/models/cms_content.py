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
from app.utils.datetime_utc import utcnow


class CmsContent(Base):
    __tablename__ = "cms_contents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="内容ID")

    # v3：内容中心与投放解耦：内容可先在“内容中心”创建（不挂栏目），再在“官网投放”页分配栏目并发布
    channel_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="栏目ID（官网投放）")

    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="标题")
    cover_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="封面图")
    summary: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="摘要")

    # v2：Markdown 作为写侧首选（编辑器输入）；content_html 作为渲染用（小程序 rich-text / 网页）
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True, comment="正文（Markdown）")
    content_html: Mapped[str] = mapped_column(Text, nullable=False, comment="正文（HTML）")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CmsContentStatus.DRAFT.value,
        comment="状态：DRAFT/PUBLISHED/OFFLINE",
    )

    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发布时间")

    # v2：按渠道发布（最小改造）
    # - status/published_at：官网（WEB）
    # - mp_status/mp_published_at：小程序（MINI_PROGRAM）
    mp_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CmsContentStatus.DRAFT.value,
        comment="小程序状态：DRAFT/PUBLISHED/OFFLINE",
    )
    mp_published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="小程序发布时间")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效开始")
    effective_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效结束")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
