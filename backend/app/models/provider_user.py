"""服务提供方后台账号（PROVIDER，v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> RBAC：PROVIDER 账号体系（阶段12落地）
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.datetime_utc import utcnow


class ProviderUser(Base):
    __tablename__ = "provider_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="服务提供方后台账号ID")
    provider_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="服务提供方主体ID")

    username: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, comment="登录用户名（唯一）"
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希（bcrypt）")

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", comment="状态：ACTIVE/SUSPENDED")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="注册手机号（角色内唯一，可选）")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
