"""服务提供方后台（provider）核心接口（阶段12，v1 最小可执行）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段12（Provider 后台服务）
- specs/health-services-platform/design.md -> RBAC 数据范围（providerId/venueId）
- specs/health-services-platform/prototypes/provider.md -> 场所信息/服务管理/排期容量/核销记录页面结构
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.enums import (
    AuditAction,
    AuditActorType,
    CommonEnabledStatus,
    ProductFulfillmentType,
    ProductStatus,
    ProviderHealthCardStatus,
    RedemptionMethod,
    RedemptionStatus,
    OrderFulfillmentStatus,
    PaymentStatus,
    VenueReviewStatus,
    VenuePublishStatus,
)
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.provider import Provider
from app.models.redemption_record import RedemptionRecord
from app.models.service_category import ServiceCategory
from app.models.taxonomy_node import TaxonomyNode
from app.models.venue import Venue
from app.models.venue_schedule import VenueSchedule
from app.models.venue_service import VenueService
from app.services.provider_auth_context import require_provider_context
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["provider"])


async def _assert_tags_available(*, session, tag_type: str, tags: list[str] | None) -> None:
    """提交审核时强校验：所选标签必须仍为 ENABLED。

    tag_type: PRODUCT|SERVICE|VENUE
    tags: 端侧保存的 tag name 列表
    """

    picked = [str(x or "").strip() for x in (tags or [])]
    picked = [x for x in picked if x]
    if not picked:
        return

    node_type = {"PRODUCT": "PRODUCT_TAG", "SERVICE": "SERVICE_TAG", "VENUE": "VENUE_TAG"}[str(tag_type)]
    rows = (
        await session.scalars(
            select(TaxonomyNode).where(
                TaxonomyNode.type == node_type,
                TaxonomyNode.status == CommonEnabledStatus.ENABLED.value,
                TaxonomyNode.name.in_(picked),
            )
        )
    ).all()
    ok_names = {str(x.name) for x in rows}
    invalid = [x for x in picked if x not in ok_names]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TAG_NOT_AVAILABLE",
                "message": "所选标签已下线或禁用，请更换后再提交",
                "details": {"invalidTags": [{"name": x} for x in invalid]},
            },
        )

def _provider_order_dto(o: Order) -> dict:
    return {
        "id": o.id,
        "userId": o.user_id,
        "orderType": o.order_type,
        "paymentStatus": o.payment_status,
        "totalAmount": float(o.total_amount),
        "fulfillmentType": o.fulfillment_type,
        "fulfillmentStatus": o.fulfillment_status,
        "goodsAmount": float(getattr(o, "goods_amount", 0.0) or 0.0),
        "shippingAmount": float(getattr(o, "shipping_amount", 0.0) or 0.0),
        "shippingAddress": getattr(o, "shipping_address_json", None),
        "shippingCarrier": getattr(o, "shipping_carrier", None),
        "shippingTrackingNo": getattr(o, "shipping_tracking_no", None),
        "shippedAt": _iso(getattr(o, "shipped_at", None)),
        "deliveredAt": _iso(getattr(o, "delivered_at", None)),
        "receivedAt": _iso(getattr(o, "received_at", None)),
        "createdAt": _iso(o.created_at),
        "paidAt": _iso(o.paid_at),
    }


class ProviderShipOrderBody(BaseModel):
    carrier: str = Field(..., min_length=1, max_length=64)
    trackingNo: str = Field(..., min_length=3, max_length=64)


async def _ensure_service_category_enabled(*, session, service_type: str) -> str:
    """v1 口径：Provider 侧写入的 serviceType 必须来自“服务大类字典”且已启用。"""

    code = str(service_type or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "serviceType 不能为空"})
    row = (
        await session.scalars(
            select(ServiceCategory)
            .where(ServiceCategory.code == code, ServiceCategory.status == CommonEnabledStatus.ENABLED.value)
            .limit(1)
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ARGUMENT", "message": f"serviceType 未在服务大类字典中启用：{code}"},
        )
    return code


async def _require_provider_health_card_approved(*, session, provider_id: str) -> None:
    """v1/v2：健行天下服务配置门禁（必须已开通/审核通过）。"""

    pr = (await session.scalars(select(Provider).where(Provider.id == provider_id).limit(1))).first()
    if pr is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "服务提供方不存在"})
    if pr.health_card_status != ProviderHealthCardStatus.APPROVED.value:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "HEALTH_CARD_NOT_OPENED",
                "message": "健行天下未开通：请先在工作台提交开通申请并通过审核",
            },
        )


def _venue_dto(v: Venue) -> dict:
    return {
        "id": v.id,
        "providerId": v.provider_id,
        "name": v.name,
        "logoUrl": v.logo_url,
        "coverImageUrl": v.cover_image_url,
        "imageUrls": v.image_urls,
        "description": v.description,
        "countryCode": v.country_code,
        "provinceCode": v.province_code,
        "cityCode": v.city_code,
        "address": v.address,
        "lat": v.lat,
        "lng": v.lng,
        "contactPhone": v.contact_phone,
        "contactPhoneMasked": (f"{str(v.contact_phone).strip()[:3]}****{str(v.contact_phone).strip()[-4:]}" if v.contact_phone and len(str(v.contact_phone).strip()) >= 7 else None),
        "businessHours": v.business_hours,
        "tags": v.tags,
        "publishStatus": v.publish_status,
        "reviewStatus": getattr(v, "review_status", None),
        "rejectReason": getattr(v, "reject_reason", None),
        "rejectedAt": _iso(getattr(v, "rejected_at", None)),
        "offlineReason": getattr(v, "offline_reason", None),
        "offlinedAt": _iso(getattr(v, "offlined_at", None)),
        "createdAt": _iso(v.created_at),
        "updatedAt": _iso(v.updated_at),
    }


@router.get("/provider/workbench/stats")
async def provider_workbench_stats(request: Request, authorization: str | None = Header(default=None)):
    """Provider 工作台统计（REQ-P1-002）。"""

    ctx = await require_provider_context(authorization=authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        total_bookings = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Booking)
                    .join(Venue, Venue.id == Booking.venue_id)
                    .where(Venue.provider_id == ctx.providerId)
                )
            ).scalar()
            or 0
        )
        total_redemptions = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(RedemptionRecord)
                    .join(Venue, Venue.id == RedemptionRecord.venue_id)
                    .where(Venue.provider_id == ctx.providerId)
                )
            ).scalar()
            or 0
        )

    return ok(
        data={"totalBookings": total_bookings, "totalRedemptions": total_redemptions},
        request_id=request.state.request_id,
    )


@router.get("/provider/venues")
async def provider_list_venues(request: Request, authorization: str | None = Header(default=None)):
    ctx = await require_provider_context(authorization=authorization)
    session_factory = get_session_factory()
    async with session_factory() as session:
        venues = (
            await session.scalars(
                select(Venue).where(Venue.provider_id == ctx.providerId).order_by(Venue.updated_at.desc())
            )
        ).all()
    return ok(
        data={
            "items": [
                {
                    "id": v.id,
                    "name": v.name,
                    "publishStatus": v.publish_status,
                    "reviewStatus": getattr(v, "review_status", None),
                    "rejectReason": getattr(v, "reject_reason", None),
                    "rejectedAt": _iso(getattr(v, "rejected_at", None)),
                    "offlineReason": getattr(v, "offline_reason", None),
                    "offlinedAt": _iso(getattr(v, "offlined_at", None)),
                }
                for v in venues
            ],
            "total": len(venues),
        },
        request_id=request.state.request_id,
    )


@router.get("/provider/venues/{id}")
async def provider_get_venue(request: Request, id: str, authorization: str | None = Header(default=None)):
    ctx = await require_provider_context(authorization=authorization)
    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (
            await session.scalars(select(Venue).where(Venue.id == id, Venue.provider_id == ctx.providerId).limit(1))
        ).first()
    if v is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})
    # 规格（TASK-P0-006）：Provider 查看联系方式属于敏感访问，需要审计（不记录电话明文）
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=str(ctx.actorType),
                actor_id=str(ctx.actorId),
                action="VIEW",
                resource_type="VENUE",
                resource_id=v.id,
                summary=f"PROVIDER 查看场所详情（含联系方式）：{v.id}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "view": "VENUE_DETAIL",
                    "includes": ["contactPhone"],
                    "contactPhoneMasked": (f"{str(v.contact_phone).strip()[:3]}****{str(v.contact_phone).strip()[-4:]}" if v.contact_phone and len(str(v.contact_phone).strip()) >= 7 else None),
                },
            )
        )
        await session.commit()
    return ok(data=_venue_dto(v), request_id=request.state.request_id)


class ProviderUpdateVenueBody(BaseModel):
    name: str | None = None
    address: str | None = None
    contactPhone: str | None = None
    businessHours: str | None = None
    countryCode: str | None = None
    provinceCode: str | None = None
    cityCode: str | None = None
    description: str | None = None
    logoUrl: str | None = None
    coverImageUrl: str | None = None
    imageUrls: list[str] | None = None
    tags: list[str] | None = None


@router.put("/provider/venues/{id}")
async def provider_update_venue(
    request: Request,
    id: str,
    body: ProviderUpdateVenueBody,
    authorization: str | None = Header(default=None),
):
    ctx = await require_provider_context(authorization=authorization)
    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (
            await session.scalars(select(Venue).where(Venue.id == id, Venue.provider_id == ctx.providerId).limit(1))
        ).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        if body.name is not None:
            if not body.name.strip():
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "name 不能为空"})
            v.name = body.name.strip()

        if body.address is not None:
            v.address = body.address.strip() if body.address.strip() else None
        if body.contactPhone is not None:
            v.contact_phone = body.contactPhone.strip() if body.contactPhone.strip() else None
        if body.businessHours is not None:
            v.business_hours = body.businessHours.strip() if body.businessHours.strip() else None

        if body.countryCode is not None:
            v.country_code = body.countryCode.strip() if body.countryCode.strip() else None
        if body.provinceCode is not None:
            v.province_code = body.provinceCode.strip() if body.provinceCode.strip() else None
        if body.cityCode is not None:
            v.city_code = body.cityCode.strip() if body.cityCode.strip() else None

        if body.description is not None:
            v.description = body.description
        if body.logoUrl is not None:
            v.logo_url = body.logoUrl.strip() if body.logoUrl.strip() else None
        if body.coverImageUrl is not None:
            v.cover_image_url = body.coverImageUrl.strip() if body.coverImageUrl.strip() else None
        if body.imageUrls is not None:
            v.image_urls = body.imageUrls
        if body.tags is not None:
            v.tags = body.tags

        await session.commit()
        await session.refresh(v)

    return ok(data=_venue_dto(v), request_id=request.state.request_id)


@router.post("/provider/venues/{id}/submit-showcase")
async def provider_submit_showcase(request: Request, id: str, authorization: str | None = Header(default=None)):
    ctx = await require_provider_context(authorization=authorization)
    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (
            await session.scalars(select(Venue).where(Venue.id == id, Venue.provider_id == ctx.providerId).limit(1))
        ).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        # 提交审核时强校验标签仍可用（ENABLED）
        await _assert_tags_available(session=session, tag_type="VENUE", tags=v.tags)

        # v1：提交展示资料前最小必填校验（spec: provider-venue-profile-v1.md）
        if not str(v.name or "").strip():
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "请先填写：场所名称"})
        if not str(v.address or "").strip():
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "请先填写：详细地址"})

        phone = str(v.contact_phone or "").strip()
        if not phone:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "请先填写：联系电话"})
        if not re.fullmatch(r"[0-9 \-]{6,20}", phone):
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_ARGUMENT", "message": "联系电话格式不正确（仅允许数字/空格/短横线，长度 6~20）"},
            )

        if not str(v.cover_image_url or "").strip():
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "请先上传：封面图"})

        desc = str(v.description or "").strip()
        if not desc:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "请先填写：场所介绍"})
        if len(desc) < 20:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "场所介绍至少 20 个字"})

        city_code = str(v.city_code or "").strip()
        if not city_code:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "请先选择：所在城市"})
        if not city_code.startswith("CITY:"):
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "城市编码不合法（必须以 CITY: 开头）"})

        # 提交后进入“待审核”；若之前被驳回，清空驳回原因（覆盖式）
        v.review_status = VenueReviewStatus.SUBMITTED.value
        # 归一：提交审核后应回到 DRAFT（避免从 OFFLINE 直接进入待审导致 Admin 无法驳回/状态卡死）
        v.publish_status = VenuePublishStatus.DRAFT.value
        v.reject_reason = None
        v.rejected_at = None

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=(
                    AuditActorType.PROVIDER_STAFF.value
                    if ctx.actorType == "PROVIDER_STAFF"
                    else AuditActorType.PROVIDER.value
                ),
                actor_id=ctx.actorId,
                action=AuditAction.PUBLISH.value,
                resource_type="VENUE_SHOWCASE",
                resource_id=v.id,
                summary="PROVIDER 提交场所展示资料",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"venueId": v.id, "providerId": ctx.providerId, "requestId": request.state.request_id},
            )
        )
        await session.commit()

    return ok(data={"success": True}, request_id=request.state.request_id)


# -----------------------------
# Product（基建联防上架商品/服务）
# -----------------------------


def _product_dto(p: Product) -> dict:
    return {
        "id": p.id,
        "providerId": p.provider_id,
        "title": p.title,
        "fulfillmentType": p.fulfillment_type,
        "categoryId": p.category_id,
        "coverImageUrl": p.cover_image_url,
        "imageUrls": p.image_urls,
        "description": p.description,
        "price": p.price or {},
        "stock": int(p.stock or 0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
        "reservedStock": int(p.reserved_stock or 0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
        "weight": float(p.weight) if (p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value and p.weight is not None) else None,
        "shippingFee": float(p.shipping_fee or 0.0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
        "tags": p.tags,
        "status": p.status,
        "rejectReason": getattr(p, "reject_reason", None),
        "rejectedAt": _iso(getattr(p, "rejected_at", None)),
        "createdAt": _iso(p.created_at),
        "updatedAt": _iso(p.updated_at),
    }


class ProviderProductPrice(BaseModel):
    original: float = Field(..., ge=0)
    employee: float | None = Field(default=None, ge=0)
    member: float | None = Field(default=None, ge=0)
    activity: float | None = Field(default=None, ge=0)


class ProviderCreateProductBody(BaseModel):
    title: str = Field(..., min_length=1)
    fulfillmentType: str = Field(..., description="SERVICE|PHYSICAL_GOODS")
    categoryId: str | None = None
    coverImageUrl: str | None = None
    imageUrls: list[str] | None = None
    description: str | None = None
    price: ProviderProductPrice
    stock: int | None = Field(default=None, ge=0)
    weight: float | None = Field(default=None, ge=0)
    shippingFee: float | None = Field(default=None, ge=0)
    tags: list[str] | None = None
    # vNow：SERVICE 商品的预约配置（用于小程序独立预约）
    serviceType: str | None = None
    bookingRequired: bool | None = None
    applicableRegions: list[str] | None = None


class ProviderUpdateProductBody(BaseModel):
    title: str | None = None
    categoryId: str | None = None
    coverImageUrl: str | None = None
    imageUrls: list[str] | None = None
    description: str | None = None
    price: ProviderProductPrice | None = None
    stock: int | None = Field(default=None, ge=0)
    weight: float | None = Field(default=None, ge=0)
    shippingFee: float | None = Field(default=None, ge=0)
    tags: list[str] | None = None
    # v1：仅允许商家侧把状态置为 PENDING_REVIEW（提交审核）或 OFF_SHELF（下架）
    status: str | None = None
    # vNow：SERVICE 商品的预约配置
    serviceType: str | None = None
    bookingRequired: bool | None = None
    applicableRegions: list[str] | None = None


@router.get("/provider/products")
async def provider_list_products(
    request: Request,
    authorization: str | None = Header(default=None),
    page: int = 1,
    pageSize: int = 20,
):
    ctx = await require_provider_context(authorization=authorization)
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Product).where(Product.provider_id == ctx.providerId).order_by(Product.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        products = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_product_dto(p) for p in products], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.post("/provider/products")
async def provider_create_product(
    request: Request,
    body: ProviderCreateProductBody,
    authorization: str | None = Header(default=None),
):
    ctx = await require_provider_context(authorization=authorization)
    if body.fulfillmentType not in {ProductFulfillmentType.SERVICE.value, ProductFulfillmentType.PHYSICAL_GOODS.value}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "fulfillmentType 不合法"})
    if body.fulfillmentType == ProductFulfillmentType.PHYSICAL_GOODS.value:
        if body.stock is None:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "物流商品必须填写 stock"})
        if body.shippingFee is None:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "物流商品必须填写 shippingFee"})
    if body.fulfillmentType == ProductFulfillmentType.SERVICE.value:
        if not (body.serviceType and body.serviceType.strip()):
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_ARGUMENT", "message": "服务型商品必须选择服务类目（serviceType）"},
            )

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 创建即提交审核：强校验标签仍可用（ENABLED）
        await _assert_tags_available(
            session=session,
            tag_type=("SERVICE" if body.fulfillmentType == ProductFulfillmentType.SERVICE.value else "PRODUCT"),
            tags=body.tags,
        )

        venue_for_service = None
        service_type_code = None
        if body.fulfillmentType == ProductFulfillmentType.SERVICE.value:
            # 单 Provider=单场所：服务型商品的预约/核销配置挂在场所服务上
            venue_for_service = (
                await session.scalars(
                    select(Venue).where(Venue.provider_id == ctx.providerId).order_by(Venue.updated_at.desc()).limit(1)
                )
            ).first()
            if venue_for_service is None:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "STATE_CONFLICT", "message": "请先完善场所信息后再创建服务型商品"},
                )
            service_type_code = await _ensure_service_category_enabled(session=session, service_type=str(body.serviceType))

        p = Product(
            id=str(uuid4()),
            provider_id=ctx.providerId,
            title=body.title.strip(),
            fulfillment_type=body.fulfillmentType,
            category_id=(body.categoryId.strip() if body.categoryId and body.categoryId.strip() else None),
            cover_image_url=(body.coverImageUrl.strip() if body.coverImageUrl and body.coverImageUrl.strip() else None),
            image_urls=body.imageUrls,
            description=body.description,
            price=body.price.model_dump(),
            stock=int(body.stock or 0),
            reserved_stock=0,
            weight=(float(body.weight) if body.weight is not None else None),
            shipping_fee=float(body.shippingFee or 0.0),
            tags=body.tags,
            status=ProductStatus.PENDING_REVIEW.value,
        )
        session.add(p)
        await session.commit()
        await session.refresh(p)

        if body.fulfillmentType == ProductFulfillmentType.SERVICE.value and venue_for_service is not None and service_type_code is not None:
            # vNow：为 SERVICE 商品生成/维护 VenueService(product_id=product.id)
            vs = (
                await session.scalars(
                    select(VenueService)
                    .where(VenueService.product_id == p.id, VenueService.venue_id == venue_for_service.id)
                    .limit(1)
                )
            ).first()
            if vs is None:
                vs = VenueService(
                    id=str(uuid4()),
                    venue_id=venue_for_service.id,
                    service_type=service_type_code,
                    title=p.title,
                    fulfillment_type=ProductFulfillmentType.SERVICE.value,
                    product_id=p.id,
                    booking_required=bool(body.bookingRequired) if body.bookingRequired is not None else False,
                    redemption_method=RedemptionMethod.BOTH.value,
                    applicable_regions=body.applicableRegions,
                    status=CommonEnabledStatus.ENABLED.value,
                )
                session.add(vs)
            else:
                vs.service_type = service_type_code
                vs.title = p.title
                vs.booking_required = bool(body.bookingRequired) if body.bookingRequired is not None else bool(vs.booking_required)
                vs.redemption_method = RedemptionMethod.BOTH.value
                vs.applicable_regions = body.applicableRegions if body.applicableRegions is not None else vs.applicable_regions
                vs.status = CommonEnabledStatus.ENABLED.value
            await session.commit()

    return ok(data=_product_dto(p), request_id=request.state.request_id)


@router.put("/provider/products/{id}")
async def provider_update_product(
    request: Request,
    id: str,
    body: ProviderUpdateProductBody,
    authorization: str | None = Header(default=None),
):
    ctx = await require_provider_context(authorization=authorization)
    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (
            await session.scalars(
                select(Product).where(Product.id == id, Product.provider_id == ctx.providerId).limit(1)
            )
        ).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "商品不存在"})

        if body.title is not None:
            if not body.title.strip():
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "title 不能为空"})
            p.title = body.title.strip()
        if body.categoryId is not None:
            p.category_id = body.categoryId.strip() if body.categoryId.strip() else None
        if body.coverImageUrl is not None:
            p.cover_image_url = body.coverImageUrl.strip() if body.coverImageUrl.strip() else None
        if body.imageUrls is not None:
            p.image_urls = body.imageUrls
        if body.description is not None:
            p.description = body.description
        if body.price is not None:
            p.price = body.price.model_dump()
        if body.stock is not None:
            if p.fulfillment_type != ProductFulfillmentType.PHYSICAL_GOODS.value:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "非物流商品不可设置 stock"})
            p.stock = int(body.stock)
        if body.weight is not None:
            if p.fulfillment_type != ProductFulfillmentType.PHYSICAL_GOODS.value:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "非物流商品不可设置 weight"})
            p.weight = float(body.weight) if body.weight is not None else None
        if body.shippingFee is not None:
            if p.fulfillment_type != ProductFulfillmentType.PHYSICAL_GOODS.value:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "非物流商品不可设置 shippingFee"})
            p.shipping_fee = float(body.shippingFee)
        if body.tags is not None:
            p.tags = body.tags

        # vNow：SERVICE 商品预约配置 → 同步到 VenueService(product_id=product.id)
        if p.fulfillment_type == ProductFulfillmentType.SERVICE.value and (
            body.serviceType is not None or body.bookingRequired is not None or body.applicableRegions is not None
        ):
            venue_for_service = (
                await session.scalars(
                    select(Venue).where(Venue.provider_id == ctx.providerId).order_by(Venue.updated_at.desc()).limit(1)
                )
            ).first()
            if venue_for_service is None:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "STATE_CONFLICT", "message": "请先完善场所信息后再配置服务预约"},
                )

            service_type_code = None
            if body.serviceType is not None:
                if not body.serviceType.strip():
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "serviceType 不能为空"})
                service_type_code = await _ensure_service_category_enabled(session=session, service_type=str(body.serviceType))

            vs = (
                await session.scalars(
                    select(VenueService)
                    .where(VenueService.product_id == p.id, VenueService.venue_id == venue_for_service.id)
                    .limit(1)
                )
            ).first()
            if vs is None:
                if service_type_code is None:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "首次配置预约需要提供 serviceType"})
                vs = VenueService(
                    id=str(uuid4()),
                    venue_id=venue_for_service.id,
                    service_type=service_type_code,
                    title=p.title,
                    fulfillment_type=ProductFulfillmentType.SERVICE.value,
                    product_id=p.id,
                    booking_required=bool(body.bookingRequired) if body.bookingRequired is not None else False,
                    redemption_method=RedemptionMethod.BOTH.value,
                    applicable_regions=body.applicableRegions,
                    status=CommonEnabledStatus.ENABLED.value,
                )
                session.add(vs)
            else:
                if service_type_code is not None:
                    vs.service_type = service_type_code
                if body.bookingRequired is not None:
                    vs.booking_required = bool(body.bookingRequired)
                if body.applicableRegions is not None:
                    vs.applicable_regions = body.applicableRegions
                vs.title = p.title
                vs.redemption_method = RedemptionMethod.BOTH.value
                vs.status = CommonEnabledStatus.ENABLED.value

        if body.status is not None:
            st = body.status.strip()
            if st not in {ProductStatus.PENDING_REVIEW.value, ProductStatus.OFF_SHELF.value}:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})
            # 提交审核：强校验标签仍可用（ENABLED）
            if st == ProductStatus.PENDING_REVIEW.value:
                await _assert_tags_available(
                    session=session,
                    tag_type=("SERVICE" if p.fulfillment_type == ProductFulfillmentType.SERVICE.value else "PRODUCT"),
                    tags=p.tags,
                )
            p.status = st

        await session.commit()
        await session.refresh(p)

    return ok(data=_product_dto(p), request_id=request.state.request_id)


# -----------------------------
# Orders（物流商品 v2：发货录入）
# -----------------------------


@router.get("/provider/orders")
async def provider_list_orders(
    request: Request,
    authorization: str | None = Header(default=None),
    fulfillmentType: str | None = None,
    paymentStatus: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    ctx = await require_provider_context(authorization=authorization)
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    # 从 order_items -> products 反查属于该 provider 的订单
    oi = aliased(OrderItem)
    p = aliased(Product)
    stmt = (
        select(Order)
        .join(oi, oi.order_id == Order.id)
        .join(p, p.id == oi.item_id)
        .where(oi.item_type == "PRODUCT", p.provider_id == ctx.providerId)
        .distinct()
        .order_by(Order.created_at.desc())
    )
    if fulfillmentType and fulfillmentType.strip():
        stmt = stmt.where(Order.fulfillment_type == fulfillmentType.strip())
    if paymentStatus and paymentStatus.strip():
        stmt = stmt.where(Order.payment_status == paymentStatus.strip())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        orders = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_provider_order_dto(x) for x in orders], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.post("/provider/orders/{id}/ship")
async def provider_ship_order(
    request: Request,
    id: str,
    body: ProviderShipOrderBody,
    authorization: str | None = Header(default=None),
):
    ctx = await require_provider_context(authorization=authorization)
    session_factory = get_session_factory()
    async with session_factory() as session:
        o = (await session.scalars(select(Order).where(Order.id == id).limit(1))).first()
        if o is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})
        if o.payment_status != PaymentStatus.PAID.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "仅已支付订单可发货"})
        if o.fulfillment_type != ProductFulfillmentType.PHYSICAL_GOODS.value:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "非物流商品订单不可发货"})
        if o.fulfillment_status not in {OrderFulfillmentStatus.NOT_SHIPPED.value, None}:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单状态不允许发货"})

        # 校验该订单确实属于该 provider（若订单混合多个 provider，则拒绝发货）
        items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all()
        product_ids = [it.item_id for it in items if it.item_type == "PRODUCT"]
        if not product_ids:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限操作该订单"})
        products = (await session.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
        provider_ids = {x.provider_id for x in products if x is not None and x.provider_id}
        if len(provider_ids) != 1 or list(provider_ids)[0] != ctx.providerId:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限操作该订单"})

        o.shipping_carrier = body.carrier.strip()
        o.shipping_tracking_no = body.trackingNo.strip()
        o.shipped_at = datetime.utcnow()
        o.fulfillment_status = OrderFulfillmentStatus.SHIPPED.value
        await session.commit()

    return ok(data=_provider_order_dto(o), request_id=request.state.request_id)


# -----------------------------
# VenueService（健行天下特供服务 + 场所服务入口）
# -----------------------------


def _venue_service_dto(vs: VenueService) -> dict:
    return {
        "id": vs.id,
        "venueId": vs.venue_id,
        "serviceType": vs.service_type,
        "title": vs.title,
        "fulfillmentType": vs.fulfillment_type,
        "productId": vs.product_id,
        "bookingRequired": bool(vs.booking_required),
        "redemptionMethod": vs.redemption_method,
        "applicableRegions": vs.applicable_regions,
        "status": vs.status,
        "createdAt": _iso(vs.created_at),
        "updatedAt": _iso(vs.updated_at),
    }


class ProviderUpsertVenueServiceBody(BaseModel):
    serviceType: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    fulfillmentType: str = Field(default=ProductFulfillmentType.SERVICE.value)
    productId: str | None = None
    bookingRequired: bool = False
    # vNow：默认双支持；历史数据仍可能为 QR_CODE/VOUCHER_CODE
    redemptionMethod: str = Field(default=RedemptionMethod.BOTH.value)
    applicableRegions: list[str] | None = None
    status: str = Field(default=CommonEnabledStatus.ENABLED.value)


@router.get("/provider/venues/{venueId}/services")
async def provider_list_venue_services(
    request: Request, venueId: str, authorization: str | None = Header(default=None)
):
    ctx = await require_provider_context(authorization=authorization)
    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (
            await session.scalars(
                select(Venue).where(Venue.id == venueId, Venue.provider_id == ctx.providerId).limit(1)
            )
        ).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        services = (
            await session.scalars(
                select(VenueService).where(VenueService.venue_id == v.id).order_by(VenueService.updated_at.desc())
            )
        ).all()

    return ok(
        data={"items": [_venue_service_dto(x) for x in services], "total": len(services)},
        request_id=request.state.request_id,
    )


@router.post("/provider/venues/{venueId}/services")
async def provider_create_venue_service(
    request: Request,
    venueId: str,
    body: ProviderUpsertVenueServiceBody,
    authorization: str | None = Header(default=None),
):
    ctx = await require_provider_context(authorization=authorization)

    if body.fulfillmentType not in {ProductFulfillmentType.SERVICE.value}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "fulfillmentType 不合法"})
    if body.redemptionMethod not in {
        RedemptionMethod.QR_CODE.value,
        RedemptionMethod.VOUCHER_CODE.value,
        RedemptionMethod.BOTH.value,
    }:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "redemptionMethod 不合法"})
    if body.status not in {CommonEnabledStatus.ENABLED.value, CommonEnabledStatus.DISABLED.value}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        await _require_provider_health_card_approved(session=session, provider_id=ctx.providerId)
        service_type_code = await _ensure_service_category_enabled(session=session, service_type=body.serviceType)

        v = (
            await session.scalars(
                select(Venue).where(Venue.id == venueId, Venue.provider_id == ctx.providerId).limit(1)
            )
        ).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        if body.productId and body.productId.strip():
            p = (
                await session.scalars(
                    select(Product)
                    .where(Product.id == body.productId.strip(), Product.provider_id == ctx.providerId)
                    .limit(1)
                )
            ).first()
            if p is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "productId 无效"})

        vs = VenueService(
            id=str(uuid4()),
            venue_id=v.id,
            service_type=service_type_code,
            title=body.title.strip(),
            fulfillment_type=body.fulfillmentType,
            product_id=(body.productId.strip() if body.productId and body.productId.strip() else None),
            booking_required=bool(body.bookingRequired),
            redemption_method=body.redemptionMethod,
            applicable_regions=body.applicableRegions,
            status=body.status,
        )
        session.add(vs)
        await session.commit()
        await session.refresh(vs)

    return ok(data=_venue_service_dto(vs), request_id=request.state.request_id)


@router.put("/provider/venues/{venueId}/services/{id}")
async def provider_update_venue_service(
    request: Request,
    venueId: str,
    id: str,
    body: ProviderUpsertVenueServiceBody,
    authorization: str | None = Header(default=None),
):
    ctx = await require_provider_context(authorization=authorization)

    if body.fulfillmentType not in {ProductFulfillmentType.SERVICE.value}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "fulfillmentType 不合法"})
    if body.redemptionMethod not in {
        RedemptionMethod.QR_CODE.value,
        RedemptionMethod.VOUCHER_CODE.value,
        RedemptionMethod.BOTH.value,
    }:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "redemptionMethod 不合法"})
    if body.status not in {CommonEnabledStatus.ENABLED.value, CommonEnabledStatus.DISABLED.value}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        await _require_provider_health_card_approved(session=session, provider_id=ctx.providerId)
        service_type_code = await _ensure_service_category_enabled(session=session, service_type=body.serviceType)

        v = (
            await session.scalars(
                select(Venue).where(Venue.id == venueId, Venue.provider_id == ctx.providerId).limit(1)
            )
        ).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        vs = (
            await session.scalars(
                select(VenueService).where(VenueService.id == id, VenueService.venue_id == v.id).limit(1)
            )
        ).first()
        if vs is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "服务不存在"})

        if body.productId and body.productId.strip():
            p = (
                await session.scalars(
                    select(Product)
                    .where(Product.id == body.productId.strip(), Product.provider_id == ctx.providerId)
                    .limit(1)
                )
            ).first()
            if p is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "productId 无效"})

        vs.service_type = service_type_code
        vs.title = body.title.strip()
        vs.fulfillment_type = body.fulfillmentType
        vs.product_id = body.productId.strip() if body.productId and body.productId.strip() else None
        vs.booking_required = bool(body.bookingRequired)
        vs.redemption_method = body.redemptionMethod
        vs.applicable_regions = body.applicableRegions
        vs.status = body.status
        await session.commit()
        await session.refresh(vs)

    return ok(data=_venue_service_dto(vs), request_id=request.state.request_id)


# -----------------------------
# VenueSchedule（排期/容量）
# -----------------------------


def _schedule_dto(s: VenueSchedule) -> dict:
    return {
        "id": s.id,
        "venueId": s.venue_id,
        "serviceType": s.service_type,
        "bookingDate": s.booking_date.strftime("%Y-%m-%d"),
        "timeSlot": s.time_slot,
        "capacity": int(s.capacity),
        "remainingCapacity": int(s.remaining_capacity),
        "status": s.status,
        "createdAt": _iso(s.created_at),
        "updatedAt": _iso(s.updated_at),
    }


class ProviderScheduleItem(BaseModel):
    serviceType: str = Field(..., min_length=1)
    bookingDate: str = Field(..., description="YYYY-MM-DD")
    timeSlot: str = Field(..., description="HH:mm-HH:mm")
    capacity: int = Field(..., ge=0)


class ProviderBatchUpsertSchedulesBody(BaseModel):
    items: list[ProviderScheduleItem]


@router.get("/provider/venues/{venueId}/schedules")
async def provider_list_schedules(
    request: Request,
    venueId: str,
    authorization: str | None = Header(default=None),
    serviceType: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    ctx = await require_provider_context(authorization=authorization)
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (
            await session.scalars(
                select(Venue).where(Venue.id == venueId, Venue.provider_id == ctx.providerId).limit(1)
            )
        ).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        stmt = select(VenueSchedule).where(VenueSchedule.venue_id == v.id)
        if serviceType and serviceType.strip():
            stmt = stmt.where(VenueSchedule.service_type == serviceType.strip())
        if dateFrom:
            try:
                df = datetime.strptime(dateFrom, "%Y-%m-%d").date()
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateFrom 格式不合法"}
                ) from exc
            stmt = stmt.where(VenueSchedule.booking_date >= df)
        if dateTo:
            try:
                dt = datetime.strptime(dateTo, "%Y-%m-%d").date()
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateTo 格式不合法"}
                ) from exc
            stmt = stmt.where(VenueSchedule.booking_date <= dt)

        stmt = stmt.order_by(VenueSchedule.booking_date.asc(), VenueSchedule.time_slot.asc())
        count_stmt = select(func.count()).select_from(stmt.subquery())

        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_schedule_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.put("/provider/venues/{venueId}/schedules/batch")
async def provider_batch_upsert_schedules(
    request: Request,
    venueId: str,
    body: ProviderBatchUpsertSchedulesBody,
    authorization: str | None = Header(default=None),
):
    ctx = await require_provider_context(authorization=authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (
            await session.scalars(
                select(Venue).where(Venue.id == venueId, Venue.provider_id == ctx.providerId).limit(1)
            )
        ).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        updated: list[VenueSchedule] = []
        for item in body.items:
            service_type = item.serviceType.strip()
            time_slot = item.timeSlot.strip()
            if not service_type or not time_slot:
                raise HTTPException(
                    status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "serviceType/timeSlot 不能为空"}
                )
            try:
                booking_date = datetime.strptime(item.bookingDate, "%Y-%m-%d").date()
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "bookingDate 格式不合法"}
                ) from exc

            existing = (
                await session.scalars(
                    select(VenueSchedule)
                    .where(
                        VenueSchedule.venue_id == v.id,
                        VenueSchedule.service_type == service_type,
                        VenueSchedule.booking_date == booking_date,
                        VenueSchedule.time_slot == time_slot,
                    )
                    .limit(1)
                )
            ).first()
            if existing is None:
                s = VenueSchedule(
                    id=str(uuid4()),
                    venue_id=v.id,
                    service_type=service_type,
                    booking_date=booking_date,
                    time_slot=time_slot,
                    capacity=int(item.capacity),
                    remaining_capacity=int(item.capacity),
                    status=CommonEnabledStatus.ENABLED.value,
                )
                session.add(s)
                updated.append(s)
                continue

            old_capacity = int(existing.capacity or 0)
            old_remaining = int(existing.remaining_capacity or 0)
            booked = old_capacity - old_remaining
            if booked < 0:
                booked = 0
            new_capacity = int(item.capacity)
            new_remaining = max(0, new_capacity - booked)

            existing.capacity = new_capacity
            existing.remaining_capacity = new_remaining
            existing.status = CommonEnabledStatus.ENABLED.value
            updated.append(existing)

        await session.commit()
        for x in updated:
            await session.refresh(x)

    return ok(data={"items": [_schedule_dto(x) for x in updated]}, request_id=request.state.request_id)


# -----------------------------
# Redemption records（核销记录）
# -----------------------------


def _redemption_dto(r: RedemptionRecord) -> dict:
    return {
        "id": r.id,
        "redemptionTime": _iso(r.redemption_time),
        "userId": r.user_id,
        "entitlementId": r.entitlement_id,
        "bookingId": r.booking_id,
        "venueId": r.venue_id,
        "serviceType": r.service_type,
        "redemptionMethod": r.redemption_method,
        "status": r.status,
        "failureReason": r.failure_reason,
        "operatorId": r.operator_id,
        "notes": r.notes,
    }


@router.get("/provider/redemptions")
async def provider_list_redemptions(
    request: Request,
    authorization: str | None = Header(default=None),
    dateFrom: str | None = None,
    dateTo: str | None = None,
    serviceType: str | None = None,
    status: str | None = None,  # SUCCESS|FAILED
    operatorId: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    ctx = await require_provider_context(authorization=authorization)
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    if (
        status
        and status.strip()
        and status.strip() not in {RedemptionStatus.SUCCESS.value, RedemptionStatus.FAILED.value}
    ):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})

    stmt = (
        select(RedemptionRecord)
        .join(Venue, Venue.id == RedemptionRecord.venue_id)
        .where(Venue.provider_id == ctx.providerId)
    )
    if serviceType and serviceType.strip():
        stmt = stmt.where(RedemptionRecord.service_type == serviceType.strip())
    if status and status.strip():
        stmt = stmt.where(RedemptionRecord.status == status.strip())
    if operatorId and operatorId.strip():
        stmt = stmt.where(RedemptionRecord.operator_id == operatorId.strip())
    if dateFrom:
        try:
            df = datetime.fromisoformat(dateFrom if len(dateFrom) > 10 else dateFrom + "T00:00:00")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateFrom 时间格式不合法"}
            ) from exc
        stmt = stmt.where(RedemptionRecord.redemption_time >= df)
    if dateTo:
        try:
            dt = datetime.fromisoformat(dateTo if len(dateTo) > 10 else dateTo + "T23:59:59")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateTo 时间格式不合法"}
            ) from exc
        stmt = stmt.where(RedemptionRecord.redemption_time <= dt)

    stmt = stmt.order_by(RedemptionRecord.redemption_time.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_redemption_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )
