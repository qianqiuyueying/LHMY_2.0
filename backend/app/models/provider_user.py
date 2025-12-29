"""服务提供方后台账号（PROVIDER，v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> RBAC：PROVIDER 账号体系（阶段12落地）
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProviderUser(Base):
    __tablename__ = "provider_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="服务提供方后台账号ID")
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="服务提供方主体ID")

    username: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, comment="登录用户名（唯一）"
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希（bcrypt）")

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", comment="状态：ACTIVE/SUSPENDED")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
