"""权益转赠记录模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段2-8.3

说明：design.md 当前仅列出 entitlement_transfers 表名，未给出字段结构。
为保证 v1 可验收，这里按“最小可执行口径”实现：
- id
- entitlementId
- fromOwnerId
- toOwnerId
- transferredAt

后续如需与审计/会员迁移/状态迁移强绑定，应先补充规格再扩展字段。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EntitlementTransfer(Base):
    __tablename__ = "entitlement_transfers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="转赠记录ID")
    entitlement_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="权益ID")

    from_owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="转出方 ownerId")
    to_owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="转入方 ownerId")

    transferred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="转赠时间")
