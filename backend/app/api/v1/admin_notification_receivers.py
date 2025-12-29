"""Admin 通知接收者搜索（v1.1）。

规格来源：
- specs/health-services-platform/admin-notifications-sending-v1.md -> 3.3 Admin：接收者搜索（v1.1）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.v1.deps import require_admin
from app.models.admin import Admin
from app.models.dealer import Dealer
from app.models.dealer_user import DealerUser
from app.models.provider import Provider
from app.models.provider_staff import ProviderStaff
from app.models.provider_user import ProviderUser
from app.models.enums import NotificationReceiverType
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["admin-notification-receivers"])


def _like(keyword: str | None) -> str | None:
    if not keyword or not keyword.strip():
        return None
    return f"%{keyword.strip()}%"


@router.get("/admin/notification-receivers")
async def admin_search_notification_receivers(
    request: Request,
    _admin=Depends(require_admin),
    receiverType: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin
    rt = str(receiverType or "").strip().upper()
    if rt not in {
        NotificationReceiverType.ADMIN.value,
        NotificationReceiverType.DEALER.value,
        NotificationReceiverType.PROVIDER.value,
        NotificationReceiverType.PROVIDER_STAFF.value,
    }:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "receiverType 不合法"})

    page = max(1, int(page))
    page_size = max(1, min(50, int(pageSize)))
    kw = _like(keyword)

    session_factory = get_session_factory()
    async with session_factory() as session:
        if rt == NotificationReceiverType.ADMIN.value:
            stmt = select(Admin).where(Admin.status == "ACTIVE")
            if kw:
                stmt = stmt.where(Admin.username.like(kw))
            stmt = stmt.order_by(Admin.created_at.desc())
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = int((await session.execute(count_stmt)).scalar() or 0)
            rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()
            items = [{"id": a.id, "receiverType": rt, "label": f"{a.username}（Admin）"} for a in rows]

        elif rt == NotificationReceiverType.DEALER.value:
            stmt = (
                select(DealerUser, Dealer.name)
                .join(Dealer, Dealer.id == DealerUser.dealer_id, isouter=True)
                .where(DealerUser.status == "ACTIVE")
            )
            if kw:
                stmt = stmt.where(DealerUser.username.like(kw) | Dealer.name.like(kw))
            stmt = stmt.order_by(DealerUser.created_at.desc())
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = int((await session.execute(count_stmt)).scalar() or 0)
            rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()
            items = [{"id": u.id, "receiverType": rt, "label": f"{u.username}（{dealer_name or '经销商'}）"} for u, dealer_name in rows]

        elif rt == NotificationReceiverType.PROVIDER.value:
            stmt = (
                select(ProviderUser, Provider.name)
                .join(Provider, Provider.id == ProviderUser.provider_id, isouter=True)
                .where(ProviderUser.status == "ACTIVE")
            )
            if kw:
                stmt = stmt.where(ProviderUser.username.like(kw) | Provider.name.like(kw))
            stmt = stmt.order_by(ProviderUser.created_at.desc())
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = int((await session.execute(count_stmt)).scalar() or 0)
            rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()
            items = [{"id": u.id, "receiverType": rt, "label": f"{u.username}（{provider_name or '服务商'}）"} for u, provider_name in rows]

        else:
            stmt = (
                select(ProviderStaff, Provider.name)
                .join(Provider, Provider.id == ProviderStaff.provider_id, isouter=True)
                .where(ProviderStaff.status == "ACTIVE")
            )
            if kw:
                stmt = stmt.where(ProviderStaff.username.like(kw) | Provider.name.like(kw) | ProviderStaff.provider_id.like(kw))
            stmt = stmt.order_by(ProviderStaff.created_at.desc())
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = int((await session.execute(count_stmt)).scalar() or 0)
            rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()
            items = [{"id": u.id, "receiverType": rt, "label": f"{u.username}（{provider_name or '服务商员工'}）"} for u, provider_name in rows]

    return ok(data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)

