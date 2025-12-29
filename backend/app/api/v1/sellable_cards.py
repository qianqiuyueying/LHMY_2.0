"""可售卡（SellableCard）读接口（供 H5）（v2.1）。

规格来源：
- specs/health-services-platform/dealer-link-sellable-cards-v1.md（v2.1）
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.models.enums import CommonEnabledStatus
from app.models.sellable_card import SellableCard
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso


router = APIRouter(tags=["sellable-cards"])

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


@router.get("/sellable-cards/{id}")
async def get_sellable_card(request: Request, id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(SellableCard).where(SellableCard.id == id).limit(1))).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "可售卡不存在"})
    if row.status != CommonEnabledStatus.ENABLED.value:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "可售卡已停用"})
    return ok(data=_dto(row), request_id=request.state.request_id)

