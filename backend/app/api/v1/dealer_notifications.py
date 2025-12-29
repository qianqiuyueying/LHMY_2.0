"""Dealer 通知列表/已读（v1）。

规格来源：
- specs/health-services-platform/admin-notifications-sending-v1.md -> 3.2 接收端：通知列表（dealer）
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.v1.deps import optional_actor
from app.models.enums import NotificationCategory, NotificationReceiverType, NotificationStatus
from app.models.notification import Notification
from app.services.rbac import ActorContext, ActorType, require_actor_types
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["dealer-notifications"])


def _dto(n: Notification) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "category": getattr(n, "category", None) or NotificationCategory.SYSTEM.value,
        "status": n.status,
        "createdAt": n.created_at.astimezone().isoformat(),
        "readAt": (n.read_at.astimezone().isoformat() if n.read_at else None),
    }


async def _require_dealer(actor: ActorContext | None) -> ActorContext:
    if actor is None:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    require_actor_types(actor=actor, allowed={ActorType.DEALER})
    return actor


@router.get("/dealer/notifications")
async def dealer_list_notifications(
    request: Request,
    actor: ActorContext | None = Depends(optional_actor),
    status: Literal["UNREAD", "READ"] | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    a = await _require_dealer(actor)
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Notification).where(
        Notification.receiver_type == NotificationReceiverType.DEALER.value,
        Notification.receiver_id == str(a.sub),
    )
    if status:
        if status not in {NotificationStatus.UNREAD.value, NotificationStatus.READ.value}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})
        stmt = stmt.where(Notification.status == str(status))

    stmt = stmt.order_by(Notification.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(data={"items": [_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


@router.post("/dealer/notifications/{id}/read")
async def dealer_mark_notification_read(
    request: Request,
    id: str,
    actor: ActorContext | None = Depends(optional_actor),
):
    a = await _require_dealer(actor)
    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        n = (
            await session.scalars(
                select(Notification)
                .where(
                    Notification.id == id,
                    Notification.receiver_type == NotificationReceiverType.DEALER.value,
                    Notification.receiver_id == str(a.sub),
                )
                .limit(1)
            )
        ).first()
        if n is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "通知不存在"})
        if n.status != NotificationStatus.READ.value:
            n.status = NotificationStatus.READ.value
            n.read_at = now
            await session.commit()
            await session.refresh(n)

    return ok(data=_dto(n), request_id=request.state.request_id)

