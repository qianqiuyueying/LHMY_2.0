"""购卡实例（Card，H5 匿名购卡 + 小程序绑定，v1）。

规格来源：
- specs/lhmy-2.0-maintenance/h5-anonymous-purchase-bind-token-v1.md

说明：
- Card 仅表达“绑定状态 + 归属用户”；权益与服务包实例的关联在业务层处理。
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CardStatus


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="卡ID")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CardStatus.UNBOUND.value,
        comment="状态：UNBOUND/BOUND",
    )

    owner_user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="归属用户ID（未绑定为空）",
    )


