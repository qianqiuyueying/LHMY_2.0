"""经销商侧：可售卡下拉列表（v2.1）。

规格来源：
- specs/health-services-platform/dealer-link-sellable-cards-v1.md（v2.1）
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from sqlalchemy import select

from app.api.v1.dealer_links import _require_dealer_or_admin_context
from app.models.enums import CommonEnabledStatus
from app.models.sellable_card import SellableCard
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso


router = APIRouter(tags=["dealer-sellable-cards"])

def _dto(x: SellableCard) -> dict:
    return {
        "id": x.id,
        "name": x.name,
        "servicePackageTemplateId": x.service_package_template_id,
        "regionLevel": x.region_level,
        "priceOriginal": float(x.price_original or 0),
        "status": x.status,
        "sort": int(x.sort or 0),
        "createdAt": _iso(x.created_at),
        "updatedAt": _iso(x.updated_at),
    }


@router.get("/dealer/sellable-cards")
async def dealer_list_sellable_cards(request: Request, authorization: str | None = Header(default=None)):
    # v1：鉴权允许 DEALER/ADMIN
    _ = await _require_dealer_or_admin_context(authorization=authorization)

    stmt = (
        select(SellableCard)
        .where(SellableCard.status == CommonEnabledStatus.ENABLED.value)
        .order_by(SellableCard.sort.desc(), SellableCard.updated_at.desc())
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (await session.scalars(stmt)).all()

    return ok(data={"items": [_dto(x) for x in rows], "total": len(rows)}, request_id=request.state.request_id)

