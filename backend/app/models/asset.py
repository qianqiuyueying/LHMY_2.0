from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="资产ID")

    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True, comment="类型：IMAGE")

    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="内容哈希（sha256）")

    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="文件大小（bytes）")
    mime: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="MIME")
    ext: Mapped[str] = mapped_column(String(16), nullable=False, default="", comment="扩展名")

    storage: Mapped[str] = mapped_column(String(16), nullable=False, default="LOCAL", comment="存储：LOCAL/OSS(预留)")
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="存储 key（如 uploads/2025/12/xxx.jpg）")
    url: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="对外 URL（/static/uploads/... 或 https://cdn/...）")

    original_filename: Mapped[str] = mapped_column(String(256), nullable=False, default="", comment="原文件名（可选）")

    created_by_actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="", comment="创建者类型")
    created_by_actor_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="创建者ID")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )


