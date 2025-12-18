"""用户企业绑定关系模型。

规格来源：
- specs/health-services-platform/design.md -> 企业绑定最小可执行口径 + 附录 B1（状态/迁移/属性10约束）
- specs/health-services-platform/prototypes/admin.md -> 绑定关系列表（绑定ID/用户/企业/状态/绑定时间）
- specs/health-services-platform/tasks.md -> 阶段2-5.3
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import UserEnterpriseBindingStatus


class UserEnterpriseBinding(Base):
    """用户企业绑定申请与审核结果。"""

    __tablename__ = "user_enterprise_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="绑定ID")

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="用户ID",
    )

    enterprise_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("enterprises.id"),
        nullable=False,
        index=True,
        comment="企业ID",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=UserEnterpriseBindingStatus.PENDING.value,
        comment="状态：PENDING/APPROVED/REJECTED",
    )

    # 绑定时间：以“用户提交申请时间”为口径（列表筛选/展示用）
    binding_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="绑定时间（提交时间）",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
