"""场所接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md ->
  - `GET /api/v1/venues`
  - `GET /api/v1/venues/{id}`
  - `GET /api/v1/venues/{id}/available-slots`
- specs/health-services-platform/design.md -> 场所模型（Venue/VenueService/VenueSchedule）
- specs/health-services-platform/tasks.md -> 阶段6-35/36

v1 说明：
- `GET /api/v1/venues` / `GET /api/v1/venues/{id}` 允许未登录访问，但仅返回 PUBLISHED 场所。
- 当 `entitlementId` 传入时，按该权益适用范围过滤场所（属性14）；出于安全性，v1 要求 USER 登录且 ownerId 必须为本人。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import or_, select

from app.models.entitlement import Entitlement
from app.models.enums import CommonEnabledStatus, VenuePublishStatus
from app.models.venue import Venue
from app.models.venue_schedule import VenueSchedule
from app.models.venue_service import VenueService
from app.api.v1.deps import optional_user, require_user
from app.services.venue_filtering_rules import (
    VenueLite,
    VenueRegion,
    filter_venues_by_entitlement,
    matches_region_filter,
)
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["venues"])


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


def _venue_list_item_dto(v: Venue) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "coverImageUrl": v.cover_image_url,
        "cityCode": v.city_code,
        "provinceCode": v.province_code,
        "countryCode": v.country_code,
        "address": v.address,
        "businessHours": v.business_hours,
        "tags": v.tags,
        "contactPhoneMasked": _mask_phone(v.contact_phone),
    }


def _venue_detail_public_dto(v: Venue) -> dict:
    return {
        "id": v.id,
        "providerId": v.provider_id,
        "name": v.name,
        "logoUrl": v.logo_url,
        "coverImageUrl": v.cover_image_url,
        "imageUrls": v.image_urls,
        "cityCode": v.city_code,
        "provinceCode": v.province_code,
        "countryCode": v.country_code,
        "description": v.description,
        "address": v.address,
        "lat": v.lat,
        "lng": v.lng,
        "businessHours": v.business_hours,
        "tags": v.tags,
        # 官网/对外展示：场所详情必须可联系（电话明文），列表仍仅返回脱敏字段
        "contactPhone": (str(v.contact_phone).strip() if v.contact_phone and str(v.contact_phone).strip() else None),
        "contactPhoneMasked": _mask_phone(v.contact_phone),
    }


def _venue_service_dto(vs: VenueService) -> dict:
    return {
        "id": vs.id,
        "title": vs.title,
        "fulfillmentType": vs.fulfillment_type,
        "productId": vs.product_id,
    }


@router.get("/venues")
async def list_venues(
    request: Request,
    authorization: str | None = Header(default=None),
    user=Depends(optional_user),
    keyword: str | None = None,
    regionLevel: str | None = None,  # CITY|PROVINCE|COUNTRY
    regionCode: str | None = None,
    taxonomyId: str | None = None,
    entitlementId: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    # 基础：仅 PUBLISHED
    stmt = select(Venue).where(Venue.publish_status == VenuePublishStatus.PUBLISHED.value)

    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Venue.name.like(kw), Venue.address.like(kw)))

    # 地区筛选（v1 最小：先拉取后用规则函数判定，避免引入复杂 SQL 拼接）
    # taxonomyId（v1 最小约束）：规格未给出 Venue 与 taxonomy 的显式关联；
    # 为保持可用性，v1 将 taxonomyId 解释为 “serviceType”，筛选存在 ENABLED 的 VenueService.serviceType==taxonomyId 的场所。
    session_factory = get_session_factory()
    async with session_factory() as session:
        if taxonomyId and taxonomyId.strip():
            vs_venue_ids = (
                await session.scalars(
                    select(VenueService.venue_id).where(
                        VenueService.service_type == taxonomyId.strip(),
                        VenueService.status == CommonEnabledStatus.ENABLED.value,
                    )
                )
            ).all()
            if not vs_venue_ids:
                return ok(
                    data={"items": [], "page": page, "pageSize": page_size, "total": 0},
                    request_id=request.state.request_id,
                )
            stmt = stmt.where(Venue.id.in_(list(set(vs_venue_ids))))

        venues = (await session.scalars(stmt.order_by(Venue.created_at.desc()))).all()

        # 地区过滤（纯函数，便于属性测试覆盖）
        venues = [
            v
            for v in venues
            if matches_region_filter(
                venue=VenueLite(
                    id=v.id,
                    region=VenueRegion(
                        country_code=v.country_code, province_code=v.province_code, city_code=v.city_code
                    ),
                ),
                region_level=regionLevel,
                region_code=regionCode,
            )
        ]

        # 权益过滤：要求登录且 ownerId 为本人
        if entitlementId and entitlementId.strip():
            if user is None:
                raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
            user_id = str(user.sub)

            e = (
                await session.scalars(select(Entitlement).where(Entitlement.id == entitlementId.strip()).limit(1))
            ).first()
            if e is None:
                raise HTTPException(status_code=404, detail={"code": "ENTITLEMENT_NOT_FOUND", "message": "权益不存在"})
            if e.owner_id != user_id:
                raise HTTPException(
                    status_code=403, detail={"code": "ENTITLEMENT_NOT_OWNED", "message": "无权限访问该权益"}
                )

            filtered = filter_venues_by_entitlement(
                venues=[
                    VenueLite(
                        id=v.id,
                        region=VenueRegion(
                            country_code=v.country_code, province_code=v.province_code, city_code=v.city_code
                        ),
                    )
                    for v in venues
                ],
                entitlement_type=e.entitlement_type,
                applicable_regions=e.applicable_regions,
                applicable_venues=e.applicable_venues,
            )
            allowed_ids = {x.id for x in filtered}
            venues = [v for v in venues if v.id in allowed_ids]

        total = len(venues)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = venues[start:end]

    return ok(
        data={
            "items": [_venue_list_item_dto(v) for v in page_items],
            "page": page,
            "pageSize": page_size,
            "total": total,
        },
        request_id=request.state.request_id,
    )


@router.get("/venues/{id}")
async def get_venue_detail(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
    user=Depends(optional_user),
    entitlementId: str | None = None,
):
    # 可选登录：登录后允许返回服务列表（services）
    user_ctx = {"userId": str(user.sub)} if user is not None else None

    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (
            await session.scalars(
                select(Venue).where(Venue.id == id, Venue.publish_status == VenuePublishStatus.PUBLISHED.value).limit(1)
            )
        ).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        data = _venue_detail_public_dto(v)

        if user_ctx:
            services = (
                await session.scalars(
                    select(VenueService).where(
                        VenueService.venue_id == v.id,
                        VenueService.status == CommonEnabledStatus.ENABLED.value,
                    )
                )
            ).all()
            data["services"] = [_venue_service_dto(x) for x in services]

            # 若传入 entitlementId，则补充 eligible 信息（v1 最小：只计算本人权益）
            if entitlementId and entitlementId.strip():
                e = (
                    await session.scalars(select(Entitlement).where(Entitlement.id == entitlementId.strip()).limit(1))
                ).first()
                if e is None:
                    raise HTTPException(
                        status_code=404, detail={"code": "ENTITLEMENT_NOT_FOUND", "message": "权益不存在"}
                    )
                if e.owner_id != user_ctx["userId"]:
                    raise HTTPException(
                        status_code=403, detail={"code": "ENTITLEMENT_NOT_OWNED", "message": "无权限访问该权益"}
                    )
                eligible = filter_venues_by_entitlement(
                    venues=[
                        VenueLite(
                            id=v.id,
                            region=VenueRegion(
                                country_code=v.country_code, province_code=v.province_code, city_code=v.city_code
                            ),
                        )
                    ],
                    entitlement_type=e.entitlement_type,
                    applicable_regions=e.applicable_regions,
                    applicable_venues=e.applicable_venues,
                )
                data["eligible"] = len(eligible) == 1
                if not data["eligible"]:
                    data["ineligibleReasonCode"] = "VENUE_NOT_AVAILABLE"

    return ok(data=data, request_id=request.state.request_id)


@router.get("/venues/{id}/available-slots")
async def get_available_slots(
    request: Request,
    id: str,
    serviceType: str,
    date: str,  # YYYY-MM-DD
    _user=Depends(require_user),
):
    # v1：要求 USER 登录（与 design.md 契约对齐）

    service_type = (serviceType or "").strip()
    if not service_type:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "serviceType 不能为空"})

    try:
        booking_date = datetime.strptime(date, "%Y-%m-%d").date()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "date 格式不合法"}) from exc

    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (
            await session.scalars(
                select(Venue).where(Venue.id == id, Venue.publish_status == VenuePublishStatus.PUBLISHED.value).limit(1)
            )
        ).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        schedules = (
            await session.scalars(
                select(VenueSchedule).where(
                    VenueSchedule.venue_id == id,
                    VenueSchedule.service_type == service_type,
                    VenueSchedule.booking_date == booking_date,
                    VenueSchedule.status == CommonEnabledStatus.ENABLED.value,
                )
            )
        ).all()

    slots = [{"timeSlot": s.time_slot, "remainingCapacity": int(s.remaining_capacity)} for s in schedules]
    slots.sort(key=lambda x: str(x["timeSlot"]))

    return ok(
        data={
            "venueId": id,
            "serviceType": service_type,
            "bookingDate": booking_date.strftime("%Y-%m-%d"),
            "slots": slots,
        },
        request_id=request.state.request_id,
    )
