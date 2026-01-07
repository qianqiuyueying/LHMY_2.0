"""绑定凭证（BindToken，v1）。

规格来源：
- specs/lhmy-2.0-maintenance/h5-anonymous-purchase-bind-token-v1.md

约束：
- token 可重复使用（在卡未绑定前）
- 有有效期（expires_at）
- 绑定成功后失效（used_at 置值）
- 生成新 token 时作废旧 token（仅限 UNBOUND；v1 用 used_at 记录作废时间）
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BindToken(Base):
    __tablename__ = "bind_tokens"

    token: Mapped[str] = mapped_column(String(128), primary_key=True, comment="绑定凭证 token")

    card_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="卡ID")

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="过期时间（UTC）")

    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="已使用/作废时间（UTC）")


