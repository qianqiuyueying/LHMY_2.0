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
from app.models.enums import ProviderHealthCardStatus, ProviderInfraCommerceStatus


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="服务提供方ID")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="服务提供方名称")

    infra_commerce_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ProviderInfraCommerceStatus.NOT_OPENED.value,
        comment="基建联防开通状态：NOT_OPENED/OPENED",
    )
    infra_commerce_agreement_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="基建联防协议勾选时间"
    )
    health_card_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ProviderHealthCardStatus.NOT_APPLIED.value,
        comment="健行天下开通状态：NOT_APPLIED/SUBMITTED/APPROVED/REJECTED",
    )
    health_card_agreement_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="健行天下协议勾选时间"
    )
    health_card_submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="健行天下申请提交时间")
    health_card_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="健行天下审核时间")
    health_card_review_notes: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="健行天下审核备注/驳回原因")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
