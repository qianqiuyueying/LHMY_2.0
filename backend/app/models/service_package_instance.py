"""高端服务卡实例（ServicePackageInstance，v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> ServicePackageInstance
- specs/health-services-platform/tasks.md -> 阶段2-8.1
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ServicePackageInstanceStatus
from app.utils.datetime_utc import utcnow


class ServicePackageInstance(Base):
    __tablename__ = "service_package_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="卡实例ID")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="订单ID")
    order_item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="订单明细ID")

    service_package_template_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="服务包模板ID（service_packages）",
    )

    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="当前持有者（裁决字段一致）")

    region_scope: Mapped[str] = mapped_column(String(32), nullable=False, comment="区域范围（见区域编码口径）")
    tier: Mapped[str] = mapped_column(String(64), nullable=False, comment="等级/阶梯")

    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="生效时间")
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="到期时间")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ServicePackageInstanceStatus.ACTIVE.value,
        comment="状态：ACTIVE/EXPIRED/TRANSFERRED/REFUNDED",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
