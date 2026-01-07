"""企业信息库模型。

规格来源：
- specs/health-services-platform/prototypes/admin.md -> 企业信息库（企业ID/企业名称/录入来源/首次出现时间/城市区域筛选）
- specs/health-services-platform/design.md -> 数据库设计（enterprises）+ 区域编码口径
- specs/health-services-platform/tasks.md -> 阶段2-5.2

说明：
- “绑定人数”在 v1 作为派生字段（可通过 bindings 统计），不作为持久化字段。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import EnterpriseSource
from app.utils.datetime_utc import utcnow


class Enterprise(Base):
    """企业信息库。"""

    __tablename__ = "enterprises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="企业ID")
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True, comment="企业名称")

    # 区域编码口径（最小可执行）：使用统一字符串编码
    country_code: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="国家编码（如 COUNTRY:CN）")
    province_code: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="省编码（如 PROVINCE:110000）")
    city_code: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="市编码（如 CITY:110100）")

    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EnterpriseSource.USER_FIRST_BINDING.value,
        comment="录入来源（用户首次绑定/导入/手工）",
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        comment="首次出现时间",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
