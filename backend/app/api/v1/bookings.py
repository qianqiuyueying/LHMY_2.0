"""预约接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md ->
  - `POST /api/v1/bookings`、`GET /api/v1/bookings`、`DELETE /api/v1/bookings/{id}`
  - `PUT /api/v1/bookings/{id}/confirm`、`GET /api/v1/provider/bookings`
  - 错误码：
    ENTITLEMENT_NOT_FOUND/ENTITLEMENT_NOT_OWNED/VENUE_NOT_AVAILABLE/
    CAPACITY_FULL/STATE_CONFLICT/BOOKING_CANCEL_WINDOW_CLOSED
- specs/health-services-platform/tasks.md -> 阶段6-37/38/39/40

v1 说明：
- v1 落地 PROVIDER/PROVIDER_STAFF 登录与数据范围裁决（阶段12）。
- 自动/人工确认模式的配置载体在规格中未明示；v1 暂使用 `system_configs.key="BOOKING_CONFIRMATION_METHOD"`：
  - valueJson 示例：`{ "method": "AUTO" }` 或 `{ "method": "MANUAL" }`
  - 默认：AUTO
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from typing import cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from app.models.booking import Booking
from app.models.audit_log import AuditLog
from app.models.entitlement import Entitlement
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.enums import (
    AuditAction,
    AuditActorType,
    BookingConfirmationMethod,
    BookingStatus,
    BookingSourceType,
    CommonEnabledStatus,
    OrderItemType,
    PaymentStatus,
    ProductFulfillmentType,
    VenuePublishStatus,
)
from app.models.system_config import SystemConfig
from app.models.venue import Venue
from app.models.venue_schedule import VenueSchedule
from app.models.venue_service import VenueService
from app.services.booking_capacity_rules import can_reserve_capacity, release_capacity, reserve_capacity
from app.services.booking_confirmation_rules import booking_state_on_create
from app.services.booking_state_machine import assert_booking_status_transition
from app.services.idempotency import IdemActorType, IdempotencyCachedResult, IdempotencyService
from app.services.provider_auth_context import try_get_provider_context
from app.services.venue_filtering_rules import VenueLite, VenueRegion, filter_venues_by_entitlement
from app.services.booking_rules import can_cancel_confirmed_booking
from app.api.v1.deps import require_user
from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.redis_client import get_redis
from app.utils.response import fail, ok
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token
from app.utils.datetime_iso import iso as _iso
from app.utils.date_ymd import ymd as _ymd

router = APIRouter(tags=["bookings"])

def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return idempotency_key.strip()


def _user_context_from_authorization(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token)
    return {"actorType": "USER", "userId": str(payload["sub"]), "channel": str(payload.get("channel", ""))}


async def _try_get_admin_context(authorization: str | None) -> dict | None:
    if not authorization:
        return None
    token = _extract_bearer_token(authorization)
    try:
        payload = decode_and_validate_admin_token(token=token)
    except HTTPException:
        return None

    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        return None
    return {"actorType": "ADMIN", "adminId": str(payload["sub"])}


async def _idempotency_replay_if_exists(
    *,
    request: Request,
    operation: str,
    actor_type: IdemActorType,
    actor_id: str,
    idempotency_key: str,
) -> JSONResponse | None:
    idem = IdempotencyService(get_redis())
    cached = await idem.get(
        operation=operation, actor_type=actor_type, actor_id=actor_id, idempotency_key=idempotency_key
    )
    if cached is None:
        return None

    if cached.success:
        payload = ok(data=cached.data, request_id=request.state.request_id)
    else:
        err = cached.error or {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "details": None}
        payload = fail(
            code=str(err.get("code", "INTERNAL_ERROR")),
            message=str(err.get("message", "服务器内部错误")),
            details=err.get("details"),
            request_id=request.state.request_id,
        )

    return JSONResponse(status_code=int(cached.status_code), content=payload)


def _booking_dto(b: Booking) -> dict:
    return {
        "id": b.id,
        "sourceType": getattr(b, "source_type", BookingSourceType.ENTITLEMENT.value),
        "entitlementId": b.entitlement_id,
        "orderId": getattr(b, "order_id", None),
        "orderItemId": getattr(b, "order_item_id", None),
        "productId": getattr(b, "product_id", None),
        "userId": b.user_id,
        "venueId": b.venue_id,
        "serviceType": b.service_type,
        "bookingDate": b.booking_date.strftime("%Y-%m-%d"),
        "timeSlot": b.time_slot,
        "status": b.status,
        "confirmationMethod": b.confirmation_method,
        "confirmedAt": _iso(b.confirmed_at),
        "cancelledAt": _iso(b.cancelled_at),
        "cancelReason": b.cancel_reason,
        "createdAt": _iso(b.created_at),
    }


async def _booking_confirmation_method_v1(*, session) -> str:
    """v1：读取全局配置，缺省 AUTO。"""

    row = (
        await session.scalars(
            select(SystemConfig)
            .where(
                SystemConfig.key == "BOOKING_CONFIRMATION_METHOD",
                SystemConfig.status == CommonEnabledStatus.ENABLED.value,
            )
            .limit(1)
        )
    ).first()
    if row is None:
        return BookingConfirmationMethod.AUTO.value
    method = str((row.value_json or {}).get("method", "")).strip().upper()
    if method in {BookingConfirmationMethod.AUTO.value, BookingConfirmationMethod.MANUAL.value}:
        return method
    return BookingConfirmationMethod.AUTO.value


class CreateBookingBody(BaseModel):
    # v1：权益预约；vNow：支持 ORDER_ITEM 预约（二选一）
    entitlementId: str | None = None
    orderId: str | None = None
    orderItemId: str | None = None
    venueId: str | None = None
    bookingDate: str  # YYYY-MM-DD
    timeSlot: str  # HH:mm-HH:mm


async def _resolve_order_item_booking_context(*, session, user_id: str, order_id: str, order_item_id: str) -> tuple[str, str, str]:
    """ORDER_ITEM 预约：解析 (venue_id, service_type, product_id)。"""

    o = (await session.scalars(select(Order).where(Order.id == order_id, Order.user_id == user_id).limit(1))).first()
    if o is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})
    if o.payment_status != PaymentStatus.PAID.value:
        raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单未支付，无法预约"})

    oi = (
        await session.scalars(select(OrderItem).where(OrderItem.id == order_item_id, OrderItem.order_id == o.id).limit(1))
    ).first()
    if oi is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单明细不存在"})
    if oi.item_type != OrderItemType.PRODUCT.value:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "该订单明细不支持预约"})

    p = (await session.scalars(select(Product).where(Product.id == oi.item_id).limit(1))).first()
    if p is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "商品不存在"})
    if p.fulfillment_type != ProductFulfillmentType.SERVICE.value:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "仅服务型商品支持预约"})

    vs = (
        await session.scalars(
            select(VenueService)
            .where(VenueService.product_id == p.id, VenueService.status == CommonEnabledStatus.ENABLED.value)
            .limit(1)
        )
    ).first()
    if vs is None:
        raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "未找到该商品对应的场所服务配置"})
    if not bool(vs.booking_required):
        raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "该服务未开启预约（bookingRequired=false）"})

    v = (
        await session.scalars(
            select(Venue).where(Venue.id == vs.venue_id, Venue.publish_status == VenuePublishStatus.PUBLISHED.value).limit(1)
        )
    ).first()
    if v is None:
        raise HTTPException(status_code=409, detail={"code": "VENUE_NOT_AVAILABLE", "message": "场所不可用"})

    return str(vs.venue_id), str(vs.service_type), str(p.id)


@router.get("/bookings/order-item-context")
async def get_booking_order_item_context(
    request: Request,
    orderId: str,
    orderItemId: str,
    user=Depends(require_user),
):
    user_id = str(user.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        venue_id, service_type, product_id = await _resolve_order_item_booking_context(
            session=session,
            user_id=user_id,
            order_id=str(orderId or "").strip(),
            order_item_id=str(orderItemId or "").strip(),
        )
    return ok(data={"venueId": venue_id, "serviceType": service_type, "productId": product_id}, request_id=request.state.request_id)


@router.post("/bookings")
async def create_booking(
    request: Request,
    body: CreateBookingBody,
    user=Depends(require_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    user_id = str(user.sub)

    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="create_booking",
        actor_type="USER",
        actor_id=user_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    entitlement_id = str(body.entitlementId or "").strip()
    order_id = str(body.orderId or "").strip()
    order_item_id = str(body.orderItemId or "").strip()
    venue_id = str(body.venueId or "").strip()

    using_entitlement = bool(entitlement_id)
    using_order_item = bool(order_id or order_item_id)
    if using_entitlement == using_order_item:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "entitlementId 与 orderId/orderItemId 必须二选一"})

    if using_order_item and (not order_id or not order_item_id):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "orderId/orderItemId 不能为空"})

    try:
        booking_date = datetime.strptime(body.bookingDate, "%Y-%m-%d").date()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "bookingDate 格式不合法"}
        ) from exc

    time_slot = body.timeSlot.strip()
    if not time_slot:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "timeSlot 不能为空"})

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        booking_source = BookingSourceType.ENTITLEMENT.value
        service_type = None
        product_id = None

        if using_entitlement:
            if not venue_id:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "venueId 不能为空"})

            e = (await session.scalars(select(Entitlement).where(Entitlement.id == entitlement_id).limit(1))).first()
            if e is None:
                raise HTTPException(status_code=404, detail={"code": "ENTITLEMENT_NOT_FOUND", "message": "权益不存在"})
            if e.owner_id != user_id:
                raise HTTPException(status_code=403, detail={"code": "ENTITLEMENT_NOT_OWNED", "message": "无权限访问该权益"})

            v = (
                await session.scalars(
                    select(Venue)
                    .where(Venue.id == venue_id, Venue.publish_status == VenuePublishStatus.PUBLISHED.value)
                    .limit(1)
                )
            ).first()
            if v is None:
                raise HTTPException(status_code=409, detail={"code": "VENUE_NOT_AVAILABLE", "message": "场所不可用"})

            eligible = filter_venues_by_entitlement(
                venues=[
                    VenueLite(
                        id=v.id,
                        region=VenueRegion(country_code=v.country_code, province_code=v.province_code, city_code=v.city_code),
                    )
                ],
                entitlement_type=e.entitlement_type,
                applicable_regions=e.applicable_regions,
                applicable_venues=e.applicable_venues,
            )
            if not eligible:
                raise HTTPException(status_code=409, detail={"code": "VENUE_NOT_AVAILABLE", "message": "场所不在适用范围内"})

            vs = (
                await session.scalars(
                    select(VenueService)
                    .where(
                        VenueService.venue_id == v.id,
                        VenueService.service_type == e.service_type,
                        VenueService.status == CommonEnabledStatus.ENABLED.value,
                    )
                    .limit(1)
                )
            ).first()
            if vs is None:
                raise HTTPException(status_code=409, detail={"code": "VENUE_NOT_AVAILABLE", "message": "场所不支持该服务"})

            service_type = str(e.service_type)
        else:
            booking_source = BookingSourceType.ORDER_ITEM.value
            venue_id, service_type, product_id = await _resolve_order_item_booking_context(
                session=session, user_id=user_id, order_id=order_id, order_item_id=order_item_id
            )

            existing = (
                await session.scalars(
                    select(Booking).where(
                        Booking.source_type == BookingSourceType.ORDER_ITEM.value,
                        Booking.order_item_id == order_item_id,
                        Booking.status.in_([BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]),
                    ).limit(1)
                )
            ).first()
            if existing is not None:
                raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "该订单已存在预约记录"})

        # 容量校验与扣减
        sched = (
            await session.scalars(
                select(VenueSchedule)
                .where(
                    VenueSchedule.venue_id == venue_id,
                    VenueSchedule.service_type == service_type,
                    VenueSchedule.booking_date == booking_date,
                    VenueSchedule.time_slot == time_slot,
                    VenueSchedule.status == CommonEnabledStatus.ENABLED.value,
                )
                .limit(1)
            )
        ).first()
        if sched is None:
            raise HTTPException(status_code=409, detail={"code": "CAPACITY_FULL", "message": "容量不足"})
        if not can_reserve_capacity(remaining_capacity=int(sched.remaining_capacity)):
            raise HTTPException(status_code=409, detail={"code": "CAPACITY_FULL", "message": "容量不足"})
        sched.remaining_capacity = reserve_capacity(remaining_capacity=int(sched.remaining_capacity))

        # 自动/人工确认（属性17）
        cm = await _booking_confirmation_method_v1(session=session)
        created_state = booking_state_on_create(confirmation_method=cm, now=now)

        b = Booking(
            id=str(uuid4()),
            source_type=booking_source,
            entitlement_id=(entitlement_id if using_entitlement else None),
            order_id=(order_id if booking_source == BookingSourceType.ORDER_ITEM.value else None),
            order_item_id=(order_item_id if booking_source == BookingSourceType.ORDER_ITEM.value else None),
            product_id=(product_id if booking_source == BookingSourceType.ORDER_ITEM.value else None),
            user_id=user_id,
            venue_id=venue_id,
            service_type=service_type,
            booking_date=booking_date,
            time_slot=time_slot,
            status=created_state.status,
            confirmation_method=created_state.confirmation_method,
            confirmed_at=created_state.confirmed_at,
            cancelled_at=None,
            cancel_reason=None,
            created_at=datetime.utcnow(),
        )
        session.add(b)
        await session.commit()

    data = _booking_dto(b)
    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="create_booking",
        actor_type="USER",
        actor_id=user_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return ok(data=data, request_id=request.state.request_id)


@router.get("/bookings")
async def list_my_bookings(
    request: Request,
    user=Depends(require_user),
    status: str | None = None,  # PENDING|CONFIRMED|CANCELLED|COMPLETED
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    user_id = str(user.sub)

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Booking).where(Booking.user_id == user_id)
    if status:
        stmt = stmt.where(Booking.status == status)
    if dateFrom:
        try:
            df = datetime.strptime(dateFrom, "%Y-%m-%d").date()
            stmt = stmt.where(Booking.booking_date >= df)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateFrom 格式不合法"})
    if dateTo:
        try:
            dt = datetime.strptime(dateTo, "%Y-%m-%d").date()
            stmt = stmt.where(Booking.booking_date <= dt)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateTo 格式不合法"})

    stmt = stmt.order_by(Booking.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_booking_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.get("/bookings/{id}")
async def get_booking_detail(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
):
    """获取预约详情（REQ-P0-003）。

    访问规则：
    - USER：仅本人预约
    - ADMIN：全量
    - PROVIDER/PROVIDER_STAFF：仅本 provider 归属场所的预约
    """

    admin_ctx = await _try_get_admin_context(authorization)
    provider_ctx = None if admin_ctx else await try_get_provider_context(authorization=authorization)
    user_ctx = None if (admin_ctx or provider_ctx) else _user_context_from_authorization(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        b = (await session.scalars(select(Booking).where(Booking.id == id).limit(1))).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "预约不存在"})

        # 权限裁决
        if user_ctx is not None and b.user_id != str(user_ctx["userId"]):
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})

        v = (await session.scalars(select(Venue).where(Venue.id == b.venue_id).limit(1))).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        if provider_ctx is not None and v.provider_id != provider_ctx.providerId:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})

        e = None
        if b.entitlement_id:
            e = (await session.scalars(select(Entitlement).where(Entitlement.id == b.entitlement_id).limit(1))).first()
            if e is None:
                raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "权益不存在"})

    return ok(
        data={
            **_booking_dto(b),
            "entitlement": (
                {
                    "id": e.id,
                    "entitlementType": e.entitlement_type,
                    "serviceType": e.service_type,
                    "status": e.status,
                    "remainingCount": int(e.remaining_count),
                    "totalCount": int(e.total_count),
                    # business date semantics (YYYY-MM-DD), not timestamp
                    "validFrom": _ymd(e.valid_from),
                    "validUntil": _ymd(e.valid_until),
                }
                if e is not None
                else None
            ),
            "venue": {
                "id": v.id,
                "name": v.name,
                "address": v.address,
                "coverImageUrl": v.cover_image_url,
                "providerId": v.provider_id,
            },
        },
        request_id=request.state.request_id,
    )


@router.delete("/bookings/{id}")
async def cancel_booking(
    request: Request,
    id: str,
    user=Depends(require_user),
):
    user_id = str(user.sub)

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        b = (
            await session.scalars(select(Booking).where(Booking.id == id, Booking.user_id == user_id).limit(1))
        ).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "预约不存在"})

        if b.status in {BookingStatus.CANCELLED.value, BookingStatus.COMPLETED.value}:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "预约状态不允许取消"})

        if b.status == BookingStatus.CONFIRMED.value:
            # 取消窗口校验（属性18）
            if not can_cancel_confirmed_booking(
                booking_date=b.booking_date, time_slot=b.time_slot, now=now.replace(tzinfo=None)
            ):
                raise HTTPException(
                    status_code=409,
                    detail={"code": "BOOKING_CANCEL_WINDOW_CLOSED", "message": "预约取消窗口已关闭"},
                )

        # 释放容量（属性19）
        sched = (
            await session.scalars(
                select(VenueSchedule)
                .where(
                    VenueSchedule.venue_id == b.venue_id,
                    VenueSchedule.service_type == b.service_type,
                    VenueSchedule.booking_date == b.booking_date,
                    VenueSchedule.time_slot == b.time_slot,
                )
                .limit(1)
            )
        ).first()
        if sched is not None:
            sched.remaining_capacity = release_capacity(
                remaining_capacity=int(sched.remaining_capacity),
                capacity=int(sched.capacity),
            )

        assert_booking_status_transition(current=b.status, target=BookingStatus.CANCELLED.value)
        b.status = BookingStatus.CANCELLED.value
        b.cancelled_at = now
        b.cancel_reason = "USER_CANCEL"
        await session.commit()

    return ok(data=_booking_dto(b), request_id=request.state.request_id)


class AdminCancelBookingBody(BaseModel):
    reason: str


@router.delete("/admin/bookings/{id}")
async def admin_cancel_booking(
    request: Request,
    id: str,
    body: AdminCancelBookingBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    admin=Depends(require_admin_phone_bound),
):
    """Admin 强制取消预约（v1 最小）。

    规格：
    - specs/health-services-platform/design.md -> E-12. Admin 强制取消预约
    """

    actor_type: IdemActorType = "ADMIN"
    actor_id = str(getattr(admin, "sub", "") or "")

    idem_key = _require_idempotency_key(idempotency_key)

    # 幂等复放（同 bookingId + idemKey）
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="admin_cancel_booking",
        actor_type=actor_type,
        actor_id=actor_id,
        idempotency_key=f"{id}:{idem_key}",
    )
    if replay is not None:
        return replay

    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "reason 不能为空"})

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        b = (await session.scalars(select(Booking).where(Booking.id == id).limit(1))).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "预约不存在"})

        # 幂等口径：已 CANCELLED -> 200 no-op（不重复写业务审计）
        if b.status == BookingStatus.CANCELLED.value:
            data0 = _booking_dto(b)
            idem = IdempotencyService(get_redis())
            await idem.set(
                operation="admin_cancel_booking",
                actor_type=actor_type,
                actor_id=actor_id,
                idempotency_key=f"{id}:{idem_key}",
                result=IdempotencyCachedResult(status_code=200, success=True, data=data0, error=None),
            )
            return ok(data=data0, request_id=request.state.request_id)

        # 非法状态流转：COMPLETED 再取消
        if b.status == BookingStatus.COMPLETED.value:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "预约已完成，禁止取消"},
            )

        before_status = b.status
        # 释放容量（属性19）
        sched = (
            await session.scalars(
                select(VenueSchedule)
                .where(
                    VenueSchedule.venue_id == b.venue_id,
                    VenueSchedule.service_type == b.service_type,
                    VenueSchedule.booking_date == b.booking_date,
                    VenueSchedule.time_slot == b.time_slot,
                )
                .limit(1)
            )
        ).first()
        if sched is not None:
            sched.remaining_capacity = release_capacity(
                remaining_capacity=int(sched.remaining_capacity),
                capacity=int(sched.capacity),
            )

        assert_booking_status_transition(current=b.status, target=BookingStatus.CANCELLED.value)
        b.status = BookingStatus.CANCELLED.value
        b.cancelled_at = now
        # 记录原因（必须填写）：避免超长
        b.cancel_reason = ("ADMIN_CANCEL:" + reason)[:255]

        # 业务审计（必做）：强制取消（reason 截断）
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=actor_id,
                action=AuditAction.UPDATE.value,
                resource_type="BOOKING",
                resource_id=b.id,
                summary=f"ADMIN 强制取消预约：{b.id}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "beforeStatus": before_status,
                    "afterStatus": BookingStatus.CANCELLED.value,
                    "reason": reason[:128],
                    "bookingDate": b.booking_date.strftime("%Y-%m-%d"),
                    "timeSlot": b.time_slot,
                    "venueId": b.venue_id,
                    "serviceType": b.service_type,
                    "userId": b.user_id,
                },
            )
        )
        await session.commit()

    data = _booking_dto(b)
    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="admin_cancel_booking",
        actor_type=actor_type,
        actor_id=actor_id,
        idempotency_key=f"{id}:{idem_key}",
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return ok(data=data, request_id=request.state.request_id)


@router.get("/admin/bookings")
async def admin_list_bookings(
    request: Request,
    status: str | None = None,
    serviceType: str | None = None,
    keyword: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    venueId: str | None = None,
    providerId: str | None = None,
    page: int = 1,
    pageSize: int = 20,
    _admin=Depends(require_admin),
):
    """Admin 预约监管查询（只读）。

    规格来源：specs-prod/admin/api-contracts.md#9A.1 GET /admin/bookings
    """

    # page/pageSize：按契约做参数错误返回（不隐式纠正）
    try:
        page_i = int(page)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "page 不合法"}) from exc
    try:
        ps_i = int(pageSize)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "pageSize 不合法"}) from exc
    if page_i < 1:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "page 必须 >= 1"})
    if ps_i not in {10, 20, 50, 100}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "pageSize 仅支持 10/20/50/100"})

    stmt = select(Booking).join(Venue, Venue.id == Booking.venue_id, isouter=True)

    if status and str(status).strip():
        s = str(status).strip().upper()
        if s not in {
            BookingStatus.PENDING.value,
            BookingStatus.CONFIRMED.value,
            BookingStatus.CANCELLED.value,
            BookingStatus.COMPLETED.value,
        }:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})
        stmt = stmt.where(Booking.status == s)

    if serviceType and str(serviceType).strip():
        stmt = stmt.where(Booking.service_type == str(serviceType).strip())

    if venueId and str(venueId).strip():
        stmt = stmt.where(Booking.venue_id == str(venueId).strip())

    if providerId and str(providerId).strip():
        stmt = stmt.where(Venue.provider_id == str(providerId).strip())

    if dateFrom:
        try:
            df = datetime.strptime(str(dateFrom), "%Y-%m-%d").date()
            stmt = stmt.where(Booking.booking_date >= df)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateFrom 格式不合法"}) from exc
    if dateTo:
        try:
            dt = datetime.strptime(str(dateTo), "%Y-%m-%d").date()
            stmt = stmt.where(Booking.booking_date <= dt)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateTo 格式不合法"}) from exc

    # keyword：匹配 bookingId / userId / venueId（等值优先）
    if keyword and str(keyword).strip():
        kw0 = str(keyword).strip()
        if len(kw0) == 36 and kw0.count("-") == 4:
            stmt = stmt.where((Booking.id == kw0) | (Booking.user_id == kw0) | (Booking.venue_id == kw0))
        else:
            kw = f"%{kw0}%"
            stmt = stmt.where((Booking.id.like(kw)) | (Booking.user_id.like(kw)) | (Booking.venue_id.like(kw)))

    stmt = stmt.order_by(Booking.booking_date.desc(), Booking.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page_i - 1) * ps_i).limit(ps_i))).all()

    return ok(
        data={"items": [_booking_dto(x) for x in rows], "page": page_i, "pageSize": ps_i, "total": total},
        request_id=request.state.request_id,
    )


@router.put("/bookings/{id}/confirm")
async def confirm_booking(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    admin_ctx = await _try_get_admin_context(authorization)
    provider_ctx = None if admin_ctx else await try_get_provider_context(authorization=authorization)
    if not admin_ctx and not provider_ctx:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})

    if admin_ctx:
        actor_type: IdemActorType = "ADMIN"
        actor_id = str(admin_ctx["adminId"])
    else:
        assert provider_ctx is not None
        actor_type = cast(IdemActorType, str(provider_ctx.actorType))
        actor_id = str(provider_ctx.actorId)

    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="confirm_booking",
        actor_type=actor_type,
        actor_id=actor_id,
        idempotency_key=f"{id}:{idem_key}",
    )
    if replay is not None:
        return replay

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(Booking)
        if provider_ctx is not None:
            # provider 数据范围：仅本 provider 的场所
            stmt = stmt.join(Venue, Venue.id == Booking.venue_id).where(Venue.provider_id == provider_ctx.providerId)
        b = (await session.scalars(stmt.where(Booking.id == id).limit(1))).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "预约不存在"})
        assert_booking_status_transition(current=b.status, target=BookingStatus.CONFIRMED.value)

        b.status = BookingStatus.CONFIRMED.value
        b.confirmed_at = now
        await session.commit()

    data = _booking_dto(b)
    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="confirm_booking",
        actor_type=actor_type,
        actor_id=actor_id,
        idempotency_key=f"{id}:{idem_key}",
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return ok(data=data, request_id=request.state.request_id)


@router.get("/provider/bookings")
async def list_provider_bookings(
    request: Request,
    authorization: str | None = Header(default=None),
    venueId: str | None = None,
    status: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    serviceType: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    admin_ctx = await _try_get_admin_context(authorization)
    provider_ctx = None if admin_ctx else await try_get_provider_context(authorization=authorization)
    if not admin_ctx and not provider_ctx:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Booking)
    if provider_ctx is not None:
        stmt = stmt.join(Venue, Venue.id == Booking.venue_id).where(Venue.provider_id == provider_ctx.providerId)
        if venueId and venueId.strip():
            stmt = stmt.where(Booking.venue_id == venueId.strip())
    if status:
        stmt = stmt.where(Booking.status == status)
    if serviceType and serviceType.strip():
        stmt = stmt.where(Booking.service_type == serviceType.strip())
    if dateFrom:
        try:
            df = datetime.strptime(dateFrom, "%Y-%m-%d").date()
            stmt = stmt.where(Booking.booking_date >= df)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateFrom 格式不合法"})
    if dateTo:
        try:
            dt = datetime.strptime(dateTo, "%Y-%m-%d").date()
            stmt = stmt.where(Booking.booking_date <= dt)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateTo 格式不合法"})

    # keyword（v1 最小）：匹配 booking.id / userId / venueId（不引入跨表 join）
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where((Booking.id.like(kw)) | (Booking.user_id.like(kw)) | (Booking.venue_id.like(kw)))

    stmt = stmt.order_by(Booking.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_booking_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.post("/provider/bookings/{id}/cancel")
async def provider_cancel_booking(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
):
    """服务提供方取消预约（v1 最小）。

    说明：
    - v1 允许服务提供方取消 PENDING/CONFIRMED 预约（属性18仅约束 USER 自助取消窗口）
    - 必须释放容量（属性19）
    """

    provider_ctx = await try_get_provider_context(authorization=authorization)
    if not provider_ctx:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        b = (
            await session.scalars(
                select(Booking)
                .join(Venue, Venue.id == Booking.venue_id)
                .where(Booking.id == id, Venue.provider_id == provider_ctx.providerId)
                .limit(1)
            )
        ).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "预约不存在"})

        if b.status in {BookingStatus.CANCELLED.value, BookingStatus.COMPLETED.value}:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "预约状态不允许取消"})

        # 释放容量（属性19）
        sched = (
            await session.scalars(
                select(VenueSchedule)
                .where(
                    VenueSchedule.venue_id == b.venue_id,
                    VenueSchedule.service_type == b.service_type,
                    VenueSchedule.booking_date == b.booking_date,
                    VenueSchedule.time_slot == b.time_slot,
                )
                .limit(1)
            )
        ).first()
        if sched is not None:
            sched.remaining_capacity = release_capacity(
                remaining_capacity=int(sched.remaining_capacity),
                capacity=int(sched.capacity),
            )

        assert_booking_status_transition(current=b.status, target=BookingStatus.CANCELLED.value)
        b.status = BookingStatus.CANCELLED.value
        b.cancelled_at = now
        b.cancel_reason = "PROVIDER_CANCEL"
        await session.commit()

    return ok(data=_booking_dto(b), request_id=request.state.request_id)
