"""系统配置模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> SystemConfig
- specs/health-services-platform/tasks.md -> 阶段2-11.3

说明：
- v1：以 key/valueJson 的形式存储配置；valueJson 由使用方校验 schema。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CommonEnabledStatus


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="配置ID")

    key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True, comment="配置Key（全局唯一）"
    )

    value_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="配置值（JSON）")

    description: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="说明")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CommonEnabledStatus.ENABLED.value,
        comment="状态：ENABLED/DISABLED",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
