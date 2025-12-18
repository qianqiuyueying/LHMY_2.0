"""预约接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> `POST /api/v1/bookings`、`GET /api/v1/bookings`、`DELETE /api/v1/bookings/{id}`
- specs/health-services-platform/design.md -> `PUT /api/v1/bookings/{id}/confirm`、`GET /api/v1/provider/bookings`
- specs/health-services-platform/design.md -> 错误码：ENTITLEMENT_NOT_FOUND/ENTITLEMENT_NOT_OWNED/VENUE_NOT_AVAILABLE/CAPACITY_FULL/STATE_CONFLICT/BOOKING_CANCEL_WINDOW_CLOSED
- specs/health-services-platform/tasks.md -> 阶段6-37/38/39/40

v1 说明：
- 目前代码库尚未落地 PROVIDER/PROVIDER_STAFF 的登录与数据范围裁决；因此 provider 侧接口暂按 ADMIN 访问（后续补齐账号体系后再收紧）。
- 自动/人工确认模式的配置载体在规格中未明示；v1 暂使用 `system_configs.key="BOOKING_CONFIRMATION_METHOD"`：
  - valueJson 示例：`{ "method": "AUTO" }` 或 `{ "method": "MANUAL" }`
  - 默认：AUTO
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from app.models.booking import Booking
from app.models.entitlement import Entitlement
from app.models.enums import (
    BookingConfirmationMethod,
    BookingStatus,
    CommonEnabledStatus,
    VenuePublishStatus,
)
from app.models.system_config import SystemConfig
from app.models.venue import Venue
from app.models.venue_schedule import VenueSchedule
from app.models.venue_service import VenueService
from app.services.booking_capacity_rules import can_reserve_capacity, release_capacity, reserve_capacity
from app.services.booking_confirmation_rules import booking_state_on_create
from app.services.idempotency import IdempotencyCachedResult, IdempotencyService
from app.services.venue_filtering_rules import VenueLite, VenueRegion, filter_venues_by_entitlement
from app.services.booking_rules import can_cancel_confirmed_booking
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.redis_client import get_redis
from app.utils.response import fail, ok

router = APIRouter(tags=["bookings"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return parts[1].strip()


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
    actor_type: str,
    actor_id: str,
    idempotency_key: str,
) -> JSONResponse | None:
    idem = IdempotencyService(get_redis())
    cached = await idem.get(operation=operation, actor_type=actor_type, actor_id=actor_id, idempotency_key=idempotency_key)
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
        "entitlementId": b.entitlement_id,
        "userId": b.user_id,
        "venueId": b.venue_id,
        "serviceType": b.service_type,
        "bookingDate": b.booking_date.strftime("%Y-%m-%d"),
        "timeSlot": b.time_slot,
        "status": b.status,
        "confirmationMethod": b.confirmation_method,
        "confirmedAt": b.confirmed_at.astimezone().isoformat() if b.confirmed_at else None,
        "cancelledAt": b.cancelled_at.astimezone().isoformat() if b.cancelled_at else None,
        "cancelReason": b.cancel_reason,
        "createdAt": b.created_at.astimezone().isoformat(),
    }


async def _booking_confirmation_method_v1(*, session) -> str:
    """v1：读取全局配置，缺省 AUTO。"""

    row = (
        await session.scalars(
            select(SystemConfig).where(SystemConfig.key == "BOOKING_CONFIRMATION_METHOD", SystemConfig.status == CommonEnabledStatus.ENABLED.value).limit(1)
        )
    ).first()
    if row is None:
        return BookingConfirmationMethod.AUTO.value
    method = str((row.value_json or {}).get("method", "")).strip().upper()
    if method in {BookingConfirmationMethod.AUTO.value, BookingConfirmationMethod.MANUAL.value}:
        return method
    return BookingConfirmationMethod.AUTO.value


class CreateBookingBody(BaseModel):
    entitlementId: str
    venueId: str
    bookingDate: str  # YYYY-MM-DD
    timeSlot: str  # HH:mm-HH:mm


@router.post("/bookings")
async def create_booking(
    request: Request,
    body: CreateBookingBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    user_ctx = _user_context_from_authorization(authorization)
    user_id = user_ctx["userId"]

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

    entitlement_id = body.entitlementId.strip()
    venue_id = body.venueId.strip()
    if not entitlement_id or not venue_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "entitlementId/venueId 不能为空"})

    try:
        booking_date = datetime.strptime(body.bookingDate, "%Y-%m-%d").date()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "bookingDate 格式不合法"}) from exc

    time_slot = body.timeSlot.strip()
    if not time_slot:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "timeSlot 不能为空"})

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        e = (await session.scalars(select(Entitlement).where(Entitlement.id == entitlement_id).limit(1))).first()
        if e is None:
            raise HTTPException(status_code=404, detail={"code": "ENTITLEMENT_NOT_FOUND", "message": "权益不存在"})
        if e.owner_id != user_id:
            raise HTTPException(status_code=403, detail={"code": "ENTITLEMENT_NOT_OWNED", "message": "无权限访问该权益"})

        v = (
            await session.scalars(
                select(Venue).where(Venue.id == venue_id, Venue.publish_status == VenuePublishStatus.PUBLISHED.value).limit(1)
            )
        ).first()
        if v is None:
            raise HTTPException(status_code=409, detail={"code": "VENUE_NOT_AVAILABLE", "message": "场所不可用"})

        # 适用范围校验（属性14）
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

        # 场所是否提供该服务类目（且启用）
        vs = (
            await session.scalars(
                select(VenueService).where(
                    VenueService.venue_id == v.id,
                    VenueService.service_type == e.service_type,
                    VenueService.status == CommonEnabledStatus.ENABLED.value,
                ).limit(1)
            )
        ).first()
        if vs is None:
            raise HTTPException(status_code=409, detail={"code": "VENUE_NOT_AVAILABLE", "message": "场所不支持该服务"})

        # 容量校验与扣减
        sched = (
            await session.scalars(
                select(VenueSchedule).where(
                    VenueSchedule.venue_id == v.id,
                    VenueSchedule.service_type == e.service_type,
                    VenueSchedule.booking_date == booking_date,
                    VenueSchedule.time_slot == time_slot,
                    VenueSchedule.status == CommonEnabledStatus.ENABLED.value,
                ).limit(1)
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
            entitlement_id=e.id,
            user_id=user_id,
            venue_id=v.id,
            service_type=e.service_type,
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
    authorization: str | None = Header(default=None),
    status: str | None = None,  # PENDING|CONFIRMED|CANCELLED|COMPLETED
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    user_ctx = _user_context_from_authorization(authorization)
    user_id = user_ctx["userId"]

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


@router.delete("/bookings/{id}")
async def cancel_booking(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
):
    user_ctx = _user_context_from_authorization(authorization)
    user_id = user_ctx["userId"]

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
            if not can_cancel_confirmed_booking(booking_date=b.booking_date, time_slot=b.time_slot, now=now.replace(tzinfo=None)):
                raise HTTPException(
                    status_code=409,
                    detail={"code": "BOOKING_CANCEL_WINDOW_CLOSED", "message": "预约取消窗口已关闭"},
                )

        # 释放容量（属性19）
        sched = (
            await session.scalars(
                select(VenueSchedule).where(
                    VenueSchedule.venue_id == b.venue_id,
                    VenueSchedule.service_type == b.service_type,
                    VenueSchedule.booking_date == b.booking_date,
                    VenueSchedule.time_slot == b.time_slot,
                ).limit(1)
            )
        ).first()
        if sched is not None:
            sched.remaining_capacity = release_capacity(
                remaining_capacity=int(sched.remaining_capacity),
                capacity=int(sched.capacity),
            )

        b.status = BookingStatus.CANCELLED.value
        b.cancelled_at = now
        b.cancel_reason = "USER_CANCEL"
        await session.commit()

    return ok(data=_booking_dto(b), request_id=request.state.request_id)


@router.put("/bookings/{id}/confirm")
async def confirm_booking(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    # v1：仅 ADMIN（PROVIDER 待账号体系补齐）
    admin_ctx = await _try_get_admin_context(authorization)
    if not admin_ctx:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})

    admin_id = str(admin_ctx["adminId"])
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="confirm_booking",
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=f"{id}:{idem_key}",
    )
    if replay is not None:
        return replay

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        b = (await session.scalars(select(Booking).where(Booking.id == id).limit(1))).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "预约不存在"})
        if b.status != BookingStatus.PENDING.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "预约状态不允许确认"})

        b.status = BookingStatus.CONFIRMED.value
        b.confirmed_at = now
        await session.commit()

    data = _booking_dto(b)
    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="confirm_booking",
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=f"{id}:{idem_key}",
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return ok(data=data, request_id=request.state.request_id)


@router.get("/provider/bookings")
async def list_provider_bookings(
    request: Request,
    authorization: str | None = Header(default=None),
    status: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    serviceType: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    # v1：仅 ADMIN（PROVIDER 待账号体系补齐）
    admin_ctx = await _try_get_admin_context(authorization)
    if not admin_ctx:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Booking)
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

