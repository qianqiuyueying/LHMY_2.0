"""服务包模板（高端服务卡模板，v1 最小可执行）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段2-6.4（区域级别、等级、服务类目×次数）
- specs/health-services-platform/prototypes/h5.md -> 高端服务卡介绍（服务范围/区域级别/等级/服务类别×次数）
- specs/health-services-platform/design.md -> 数据库设计（service_packages / package_services）

说明：design.md 未给出 template 的完整接口定义，因此此处仅实现任务清单与原型明确出现的最小字段。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.datetime_utc import utcnow


class ServicePackage(Base):
    __tablename__ = "service_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="服务包模板ID")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="名称")

    # 区域级别（最小：字符串标识，具体枚举可后续补规格）
    region_level: Mapped[str] = mapped_column(String(16), nullable=False, default="CITY", comment="区域级别")

    # 等级/阶梯（最小：字符串标识）
    tier: Mapped[str] = mapped_column(String(64), nullable=False, default="DEFAULT", comment="等级")

    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="说明")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )
