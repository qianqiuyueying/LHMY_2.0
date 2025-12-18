"""审计日志模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> AuditLog
- specs/health-services-platform/tasks.md -> 阶段2-11.1

约束：
- v1：仅记录必要元数据，不存敏感明文。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AuditAction, AuditActorType


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="审计ID")

    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default=AuditActorType.ADMIN.value, comment="操作者类型")
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="操作者ID")

    action: Mapped[str] = mapped_column(String(32), nullable=False, default=AuditAction.CREATE.value, comment="动作")

    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="资源类型")
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="资源ID")

    summary: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="摘要")

    ip: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="IP")
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="UserAgent")

    # 注意：SQLAlchemy Declarative API 中 metadata 为保留属性名，需避开
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="元数据（禁止存敏感明文）",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
