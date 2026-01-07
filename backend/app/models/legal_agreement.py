from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import LegalAgreementStatus
from app.utils.datetime_utc import utcnow


class LegalAgreement(Base):
    __tablename__ = "legal_agreements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="协议ID")
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="协议唯一编码")

    title: Mapped[str] = mapped_column(String(256), nullable=False, default="", comment="标题")
    # v2：写侧首选 Markdown；读侧/渲染侧仍用 HTML（小程序 rich-text / H5 v-html）
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Markdown 内容")
    content_html: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="HTML 内容")
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="0", comment="版本号")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=LegalAgreementStatus.DRAFT.value,
        comment="状态：DRAFT/PUBLISHED/OFFLINE",
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发布时间")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )


