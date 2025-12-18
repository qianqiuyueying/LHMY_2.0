"""服务提供方主体（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 服务提供方主体（Provider，v1 最小可执行）

说明：
- v1 仅承载 `id/name`，用于为商品详情等返回 `provider.name` 提供稳定数据来源。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="服务提供方ID")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="服务提供方名称")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

