"""Admin 账号模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> admin 认证：Admin 账号数据模型（v1）
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="管理员ID")
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="登录用户名（唯一）")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希（bcrypt）")

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", comment="状态：ACTIVE/SUSPENDED")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="手机号（用于2FA，可选）")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

