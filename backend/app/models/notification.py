"""消息通知记录模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> Notification
- specs/health-services-platform/tasks.md -> 阶段2-11.4

说明：
- v1：仅记录站内通知元数据，不要求与短信/推送打通。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import NotificationReceiverType, NotificationStatus


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="通知ID")

    receiver_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=NotificationReceiverType.USER.value,
        comment="接收者类型",
    )

    receiver_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="接收者ID")

    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="内容")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=NotificationStatus.UNREAD.value,
        comment="状态：UNREAD/READ",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="已读时间")
