"""用户收货地址簿（物流商品 v2）。

规格来源：
- specs/health-services-platform/tasks.md -> REQ-ECOMMERCE-P0-001（地址簿）
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserAddress(Base):
    __tablename__ = "user_addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="地址ID")
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="用户ID")

    receiver_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="收件人姓名")
    receiver_phone: Mapped[str] = mapped_column(String(32), nullable=False, comment="收件人手机号")

    country_code: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="国家编码（如 COUNTRY:CN）")
    province_code: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="省编码（如 PROVINCE:110000）")
    city_code: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="市编码（如 CITY:110100）")
    district_code: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="区县编码（可选）")

    address_line: Mapped[str] = mapped_column(String(256), nullable=False, comment="详细地址")
    postal_code: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="邮编")

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否默认地址")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )


