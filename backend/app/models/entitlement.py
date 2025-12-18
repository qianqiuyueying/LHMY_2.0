"""权益模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> Entitlement
- specs/health-services-platform/tasks.md -> 阶段2-8.2

注意：ownerId 为唯一裁决字段（属性22）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import EntitlementStatus, EntitlementType


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="权益ID")

    # userId 为兼容/查询保留字段；语义等同 ownerId（业务逻辑统一使用 ownerId）
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="用户ID（与 ownerId 一致）")
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="订单ID")

    entitlement_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EntitlementType.VOUCHER.value,
        comment="类型：VOUCHER/SERVICE_PACKAGE",
    )

    service_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="服务类目标识")

    remaining_count: Mapped[int] = mapped_column(nullable=False, default=0, comment="剩余次数")
    total_count: Mapped[int] = mapped_column(nullable=False, default=0, comment="总次数")

    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="生效时间")
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="到期时间")

    applicable_venues: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="适用场所")
    applicable_regions: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="适用区域")

    # v1：存储二维码 payload 文本（非图片）
    qr_code: Mapped[str] = mapped_column(String(2048), nullable=False, comment="二维码payload")
    voucher_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="券码")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=EntitlementStatus.ACTIVE.value,
        comment="状态：ACTIVE/USED/EXPIRED/TRANSFERRED/REFUNDED",
    )

    service_package_instance_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="服务包实例ID（仅 entitlementType=SERVICE_PACKAGE）",
    )

    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="当前持有者（唯一裁决字段）")

    activator_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="激活者")
    current_user_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", comment="当前使用者")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
