"""用户模型。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> 用户模型（interface User）
- specs/health-services-platform/tasks.md -> 阶段2-5.1

说明：
- v1：phone/unionid/openid 允许为空（跨端登录/合并见后续阶段3）。
- identities 允许叠加（MEMBER/EMPLOYEE）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """用户基础信息。"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="用户ID")

    # v1：跨端主键以 unionid 为准；phone 在绑定前可为空
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True, comment="手机号")
    openid: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="微信 openid（小程序端必返）"
    )
    unionid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, comment="微信 unionid")

    nickname: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="昵称")
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="头像")

    # 身份可叠加：MEMBER/EMPLOYEE
    identities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, comment="身份数组")

    # 企业绑定（v1：需 admin 审核通过后才生效；字段含义见企业绑定服务）
    enterprise_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="企业ID")
    enterprise_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="企业名称（冗余快照）")
    binding_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="绑定生效时间")

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
