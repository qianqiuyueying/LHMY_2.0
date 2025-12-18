"""服务包模板包含的服务类别×次数（v1 最小可执行）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段2-6.4
- specs/health-services-platform/design.md -> 数据库设计（package_services）
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PackageService(Base):
    __tablename__ = "package_services"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="明细ID")
    service_package_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_packages.id"),
        nullable=False,
        index=True,
        comment="服务包模板ID",
    )

    # serviceType 业务口径：建议使用稳定 code
    service_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="服务类目标识")
    total_count: Mapped[int] = mapped_column(nullable=False, default=1, comment="次数")
