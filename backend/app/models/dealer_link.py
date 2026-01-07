"""经销商链接模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> DealerLink
- specs/health-services-platform/design.md -> 经销商参数签名（sign）规则
- specs/health-services-platform/tasks.md -> 阶段2-10.3
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import DealerLinkStatus
from app.utils.datetime_utc import utcnow


class DealerLink(Base):
    __tablename__ = "dealer_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="链接ID")

    dealer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="归属经销商ID")

    # v2.1：链接不再强依赖商品ID（仅需 sellableCardId）；历史字段保留兼容
    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="高端服务卡商品ID（可为空）")

    # v1.2：支持“可售卡配置（sellableCardId）”用于 H5 下单参数解耦（经销商选卡售卖）
    sellable_card_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True, comment="可售卡ID（sellableCardId，可为空）"
    )

    campaign: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="活动/批次")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=DealerLinkStatus.ENABLED.value,
        comment="状态：ENABLED/DISABLED/EXPIRED",
    )

    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效时间")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="到期时间")

    url: Mapped[str] = mapped_column(String(2048), nullable=False, comment="投放URL（示例/模板）")

    uv: Mapped[int | None] = mapped_column(nullable=True, comment="访问UV（可为空）")
    paid_count: Mapped[int | None] = mapped_column(nullable=True, comment="支付数（可为空）")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
