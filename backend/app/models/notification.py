"""消息通知记录模型（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 数据模型 -> Notification
- specs/health-services-platform/tasks.md -> 阶段2-11.4

说明：
- v1：仅记录站内通知元数据，不要求与短信/推送打通。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import NotificationCategory, NotificationReceiverType, NotificationStatus


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="通知ID")

    sender_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="发送者类型（v1：手工发送固定 ADMIN；历史系统通知可为空）",
    )
    sender_id: Mapped[str | None] = mapped_column(String(36), nullable=True, comment="发送者ID（adminId，可空）")

    receiver_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=NotificationReceiverType.USER.value,
        comment="接收者类型",
    )

    receiver_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="接收者ID")

    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="内容")

    category: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=NotificationCategory.SYSTEM.value,
        comment="类别：SYSTEM/ACTIVITY/OPS",
    )
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="扩展元数据（JSON，可空）")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=NotificationStatus.UNREAD.value,
        comment="状态：UNREAD/READ",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="已读时间")
