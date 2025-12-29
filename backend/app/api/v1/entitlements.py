"""权益接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> `GET /api/v1/entitlements`、`GET /api/v1/entitlements/{id}`
- specs/health-services-platform/design.md -> 数据范围：USER 仅 ownerId；ADMIN 全量
- specs/health-services-platform/tasks.md -> 阶段5-30

说明：
- v1 仅落地 USER/ADMIN（PROVIDER/PROVIDER_STAFF 的数据范围在对应账号体系阶段补齐）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from typing import cast

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.entitlement import Entitlement
from app.models.entitlement_transfer import EntitlementTransfer
from app.models.enums import (
    AuditAction,
    AuditActorType,
    BookingStatus,
    CommonEnabledStatus,
    EntitlementStatus,
    EntitlementType,
    RedemptionMethod,
    RedemptionStatus,
    ServicePackageInstanceStatus,
)
from app.models.redemption_record import RedemptionRecord
from app.models.service_package_instance import ServicePackageInstance
from app.models.venue import Venue
from app.models.venue_service import VenueService
from app.services.entitlement_activation_rules import apply_entitlement_activation
from app.services.entitlement_qr_signing import build_payload_text, sign_payload
from app.services.entitlement_qr_signing import verify_payload_text
from app.services.entitlement_state_machine import assert_entitlement_status_transition
from app.services.booking_state_machine import assert_booking_status_transition
from app.services.booking_redeem_rules import can_redeem_with_booking_requirement
from app.services.idempotency import IdemActorType, IdempotencyCachedResult, IdempotencyService
from app.services.entitlement_redeem_rules import apply_redeem
from app.services.provider_auth_context import try_get_provider_context
from app.services.rbac import ActorType, parse_actor_from_bearer_token, require_actor_types
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.redis_client import get_redis
from app.utils.response import fail, ok
from app.utils.settings import settings
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["entitlements"])

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


def _user_context_from_authorization(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token)
    return {"actorType": "USER", "userId": str(payload["sub"]), "channel": str(payload.get("channel", ""))}


def _entitlement_dto(e: Entitlement) -> dict:
    return {
        "id": e.id,
        "userId": e.user_id,
        "orderId": e.order_id,
        "entitlementType": e.entitlement_type,
        "serviceType": e.service_type,
        "remainingCount": int(e.remaining_count),
        "totalCount": int(e.total_count),
        "validFrom": e.valid_from.astimezone().isoformat(),
        "validUntil": e.valid_until.astimezone().isoformat(),
        "applicableVenues": e.applicable_venues,
        "applicableRegions": e.applicable_regions,
        "qrCode": e.qr_code,
        "voucherCode": e.voucher_code,
        "status": e.status,
        "servicePackageInstanceId": e.service_package_instance_id,
        "ownerId": e.owner_id,
        "createdAt": e.created_at.astimezone().isoformat(),
    }


def _entitlement_dto_admin_safe(e: Entitlement) -> dict:
    """Admin 场景：禁止返回可用凭证明文（qrCode/voucherCode）。"""

    d = _entitlement_dto(e)
    d.pop("qrCode", None)
    d.pop("voucherCode", None)
    return d


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return idempotency_key.strip()


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


def _voucher_code_v1() -> str:
    return uuid4().hex[:16].upper()


def _qr_payload_v1(*, entitlement_id: str, voucher_code: str) -> str:
    now_ts = int(datetime.now(tz=UTC).timestamp())
    nonce = uuid4().hex
    sign = sign_payload(
        secret=settings.entitlement_qr_sign_secret,
        entitlement_id=entitlement_id,
        voucher_code=voucher_code,
        ts=now_ts,
        nonce=nonce,
    )
    return build_payload_text(
        entitlement_id=entitlement_id, voucher_code=voucher_code, ts=now_ts, nonce=nonce, sign=sign
    )


class RedeemEntitlementBody(BaseModel):
    venueId: str
    redemptionMethod: str  # QR_CODE|VOUCHER_CODE
    voucherCode: str | None = None


@router.post("/entitlements/{id}/redeem")
async def redeem_entitlement(
    request: Request,
    id: str,
    body: RedeemEntitlementBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """核销权益（v1 最小）。

    v1 权限口径（已确认）：
    - 仅 ADMIN 可核销（PROVIDER/PROVIDER_STAFF 待账号体系补齐后开放）

    v1 入参口径（已确认）：
    - redemptionMethod=QR_CODE：voucherCode 字段承载“完整二维码 payload 文本”，用于验签
    - redemptionMethod=VOUCHER_CODE：voucherCode 字段承载“券码本身”，用于比对
    """

    admin_ctx = await _try_get_admin_context(authorization)
    provider_ctx = None if admin_ctx else await try_get_provider_context(authorization=authorization)
    if not admin_ctx and not provider_ctx:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})

    if admin_ctx:
        actor_type: IdemActorType = "ADMIN"
        operator_id = str(admin_ctx["adminId"])
    else:
        assert provider_ctx is not None
        actor_type = cast(IdemActorType, str(provider_ctx.actorType))
        operator_id = str(provider_ctx.actorId)

    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="redeem_entitlement",
        actor_type=actor_type,
        actor_id=operator_id,
        idempotency_key=f"{id}:{idem_key}",
    )
    if replay is not None:
        return replay

    venue_id = body.venueId.strip()
    if not venue_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "venueId 不能为空"})

    if body.redemptionMethod not in {
        RedemptionMethod.QR_CODE.value,
        RedemptionMethod.VOUCHER_CODE.value,
        RedemptionMethod.BOTH.value,
    }:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "redemptionMethod 不合法"})

    provided = (body.voucherCode or "").strip()
    if not provided:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "voucherCode 不能为空"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        e = (await session.scalars(select(Entitlement).where(Entitlement.id == id).limit(1))).first()
        if e is None:
            raise HTTPException(status_code=404, detail={"code": "ENTITLEMENT_NOT_FOUND", "message": "权益不存在"})

        before_remaining = int(e.remaining_count)
        before_entitlement_status = str(e.status or "")

        # 状态/有效期/次数校验
        if e.status != EntitlementStatus.ACTIVE.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "权益状态不允许核销"})

        # DB 中的 datetime(v1) 为 naive（UTC 存储）；与 now(aware) 比较前需统一时区口径
        now = datetime.now(tz=UTC)
        valid_from = e.valid_from.replace(tzinfo=UTC) if e.valid_from and e.valid_from.tzinfo is None else e.valid_from
        valid_until = (
            e.valid_until.replace(tzinfo=UTC) if e.valid_until and e.valid_until.tzinfo is None else e.valid_until
        )

        if valid_from and valid_from > now:
            raise HTTPException(status_code=409, detail={"code": "REDEEM_NOT_ALLOWED", "message": "权益未生效"})
        if valid_until and valid_until <= now:
            raise HTTPException(status_code=409, detail={"code": "REDEEM_NOT_ALLOWED", "message": "权益已过期"})
        if int(e.remaining_count) <= 0:
            raise HTTPException(status_code=409, detail={"code": "REDEEM_NOT_ALLOWED", "message": "权益次数不足"})

        # 场所服务校验：服务类目必须在该场所可提供，且核销方式匹配
        # provider 数据范围：venueId 必须归属本 provider（ADMIN 可跨主体）
        if provider_ctx is not None:
            owned = (
                await session.scalars(
                    select(Venue).where(Venue.id == venue_id, Venue.provider_id == provider_ctx.providerId).limit(1)
                )
            ).first()
            if owned is None:
                raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})

        vs = (
            await session.scalars(
                select(VenueService).where(
                    VenueService.venue_id == venue_id,
                    VenueService.service_type == e.service_type,
                    VenueService.status == CommonEnabledStatus.ENABLED.value,
                )
            )
        ).first()
        if vs is None:
            raise HTTPException(status_code=409, detail={"code": "REDEEM_NOT_ALLOWED", "message": "场所不支持该服务"})
        # vNow：场所服务配置允许 BOTH，表示同时支持扫码/券码；兼容历史单选配置
        if vs.redemption_method not in {body.redemptionMethod, RedemptionMethod.BOTH.value}:
            raise HTTPException(status_code=409, detail={"code": "REDEEM_NOT_ALLOWED", "message": "核销方式不匹配"})

        # 预约前置（属性16）
        booking = None
        if bool(vs.booking_required):
            booking = (
                await session.scalars(
                    select(Booking).where(
                        Booking.entitlement_id == e.id,
                        Booking.venue_id == venue_id,
                        Booking.status == BookingStatus.CONFIRMED.value,
                    )
                )
            ).first()
            if not can_redeem_with_booking_requirement(
                booking_required=True, has_confirmed_booking=booking is not None
            ):
                raise HTTPException(status_code=409, detail={"code": "BOOKING_REQUIRED", "message": "需要先预约"})

        # 二维码/券码校验
        if body.redemptionMethod == RedemptionMethod.QR_CODE.value:
            now_ts = int(now.timestamp())
            vr = verify_payload_text(secret=settings.entitlement_qr_sign_secret, payload_text=provided, now_ts=now_ts)
            if not vr.ok:
                raise HTTPException(
                    status_code=403, detail={"code": vr.error_code or "QR_SIGN_INVALID", "message": "二维码签名无效"}
                )
            assert vr.parts is not None
            if vr.parts.entitlement_id != e.id or vr.parts.voucher_code != e.voucher_code:
                raise HTTPException(status_code=403, detail={"code": "QR_SIGN_INVALID", "message": "二维码签名无效"})
        else:
            # VOUCHER_CODE：比对券码本身
            if provided != e.voucher_code:
                raise HTTPException(status_code=409, detail={"code": "REDEEM_NOT_ALLOWED", "message": "券码不正确"})

        # 执行核销：成功才扣次数（属性15）
        rr = RedemptionRecord(
            id=str(uuid4()),
            entitlement_id=e.id,
            booking_id=booking.id if booking else None,
            user_id=e.owner_id,
            venue_id=venue_id,
            service_type=e.service_type,
            redemption_method=body.redemptionMethod,
            status=RedemptionStatus.SUCCESS.value,
            failure_reason=None,
            operator_id=operator_id,
            redemption_time=now,
            service_completed_at=now,
            notes=None,
        )
        session.add(rr)

        new_state = apply_redeem(
            entitlement_type=e.entitlement_type, remaining_count=int(e.remaining_count), success=True
        )
        e.remaining_count = int(new_state.remaining_count)
        if str(new_state.status) != str(e.status):
            assert_entitlement_status_transition(current=e.status, target=str(new_state.status))
            e.status = new_state.status

        after_remaining = int(e.remaining_count)
        after_entitlement_status = str(e.status or "")

        # 属性23：权益激活不可逆性（v1 最小落地）
        # 口径：一旦 activator_id 被写入（非空），后续流程不得将其恢复为空；重复写入保持首次值。
        e.activator_id = apply_entitlement_activation(current_activator_id=e.activator_id, activator_id=operator_id)
        # current_user_id：v1 默认等同 ownerId；若历史为空则补齐
        if not (e.current_user_id or "").strip():
            e.current_user_id = e.owner_id

        # v1：核销成功可派生“预约完成”
        if booking is not None:
            assert_booking_status_transition(current=booking.status, target=BookingStatus.COMPLETED.value)
            booking.status = BookingStatus.COMPLETED.value

        # 审计（你已拍板：核销必须可审计；幂等复放不重复写）
        audit_actor_type = (
            AuditActorType.ADMIN.value
            if actor_type == "ADMIN"
            else (AuditActorType.PROVIDER.value if actor_type == "PROVIDER" else AuditActorType.PROVIDER_STAFF.value)
        )
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=audit_actor_type,
                actor_id=str(operator_id),
                action=AuditAction.UPDATE.value,
                resource_type="ENTITLEMENT_REDEEM",
                resource_id=str(e.id),
                summary="权益核销（扣减次数）",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "venueId": venue_id,
                    "serviceType": e.service_type,
                    "redemptionMethod": body.redemptionMethod,
                    "operatorType": actor_type,
                    "operatorId": operator_id,
                    "beforeRemaining": before_remaining,
                    "afterRemaining": after_remaining,
                    "beforeEntitlementStatus": before_entitlement_status,
                    "afterEntitlementStatus": after_entitlement_status,
                    "redemptionRecordId": rr.id,
                    "bookingId": (booking.id if booking else None),
                },
            )
        )

        await session.commit()

    data = {
        "redemptionRecordId": rr.id,
        "entitlementId": id,
        "status": RedemptionStatus.SUCCESS.value,
        "remainingCount": int(after_remaining),
        "entitlementStatus": after_entitlement_status,
    }

    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="redeem_entitlement",
        actor_type=actor_type,
        actor_id=operator_id,
        idempotency_key=f"{id}:{idem_key}",
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )

    return ok(data=data, request_id=request.state.request_id)


@router.get("/entitlements")
async def list_entitlements(
    request: Request,
    authorization: str | None = Header(default=None),
    type: str | None = None,  # noqa: A002
    status: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    # USER/ADMIN 皆可；其余 actor（DEALER/PROVIDER）必须 403；未携带/无效 token 401
    token = _extract_bearer_token(authorization)
    actor = await parse_actor_from_bearer_token(token=token, redis=get_redis())
    require_actor_types(actor=actor, allowed={ActorType.ADMIN, ActorType.USER})
    is_admin = actor.actor_type == ActorType.ADMIN

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Entitlement)
    if not is_admin:
        stmt = stmt.where(Entitlement.owner_id == str(actor.sub))
    if type:
        stmt = stmt.where(Entitlement.entitlement_type == type)
    if status:
        stmt = stmt.where(Entitlement.status == status)
    stmt = stmt.order_by(Entitlement.created_at.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={
            "items": [(_entitlement_dto_admin_safe(x) if is_admin else _entitlement_dto(x)) for x in rows],
            "page": page,
            "pageSize": page_size,
            "total": total,
        },
        request_id=request.state.request_id,
    )


@router.get("/entitlements/{id}")
async def get_entitlement_detail(request: Request, id: str, authorization: str | None = Header(default=None)):
    token = _extract_bearer_token(authorization)
    actor = await parse_actor_from_bearer_token(token=token, redis=get_redis())
    require_actor_types(actor=actor, allowed={ActorType.ADMIN, ActorType.USER})
    is_admin = actor.actor_type == ActorType.ADMIN

    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(Entitlement).where(Entitlement.id == id).limit(1)
        if not is_admin:
            stmt = stmt.where(Entitlement.owner_id == str(actor.sub))
        e = (await session.scalars(stmt)).first()
        if e is None:
            raise HTTPException(status_code=404, detail={"code": "ENTITLEMENT_NOT_FOUND", "message": "权益不存在"})

    return ok(data=(_entitlement_dto_admin_safe(e) if is_admin else _entitlement_dto(e)), request_id=request.state.request_id)


class TransferEntitlementBody(BaseModel):
    targetUserId: str


@router.post("/entitlements/{id}/transfer")
async def transfer_entitlement(
    request: Request,
    id: str,
    body: TransferEntitlementBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """转赠权益（v1 最小）。

    规格口径：
    - USER：仅可转赠本人权益（ownerId 裁决）
    - 服务包权益：以同一张 ServicePackageInstance 为转赠范围（属性8）
    """

    admin_ctx = await _try_get_admin_context(authorization)
    user_ctx = None if admin_ctx else _user_context_from_authorization(authorization)

    if admin_ctx:
        actor_type: IdemActorType = "ADMIN"
        actor_id = str(admin_ctx["adminId"])
    else:
        actor_type = "USER"
        assert user_ctx is not None
        actor_id = str(user_ctx["userId"])

    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="transfer_entitlement",
        actor_type=actor_type,
        actor_id=actor_id,
        idempotency_key=f"{id}:{idem_key}",
    )
    if replay is not None:
        return replay

    target_user_id = body.targetUserId.strip()
    if not target_user_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "targetUserId 不能为空"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(Entitlement).where(Entitlement.id == id).limit(1)
        if user_ctx:
            stmt = stmt.where(Entitlement.owner_id == user_ctx["userId"])
        e = (await session.scalars(stmt)).first()
        if e is None:
            raise HTTPException(status_code=404, detail={"code": "ENTITLEMENT_NOT_FOUND", "message": "权益不存在"})

        if e.owner_id == target_user_id:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "不可转赠给自己"})

        if e.status != EntitlementStatus.ACTIVE.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "权益状态不允许转赠"})

        now = datetime.now(tz=UTC)

        # SERVICE_PACKAGE：转赠以“同一张卡实例”为范围（属性8）
        if e.entitlement_type == EntitlementType.SERVICE_PACKAGE.value and e.service_package_instance_id:
            sp = (
                await session.scalars(
                    select(ServicePackageInstance)
                    .where(ServicePackageInstance.id == e.service_package_instance_id)
                    .limit(1)
                )
            ).first()
            if sp is None:
                raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "服务包实例不存在"})

            entitlements = (
                await session.scalars(
                    select(Entitlement).where(Entitlement.service_package_instance_id == e.service_package_instance_id)
                )
            ).all()
            if not entitlements:
                raise HTTPException(status_code=404, detail={"code": "ENTITLEMENT_NOT_FOUND", "message": "权益不存在"})

            if any(x.remaining_count != x.total_count for x in entitlements):
                raise HTTPException(
                    status_code=409, detail={"code": "STATE_CONFLICT", "message": "服务包已使用，不可转赠"}
                )

            entitlement_ids = [x.id for x in entitlements]
            redeemed_count = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(RedemptionRecord)
                        .where(
                            RedemptionRecord.entitlement_id.in_(entitlement_ids),
                            RedemptionRecord.status == RedemptionStatus.SUCCESS.value,
                        )
                    )
                ).scalar()
                or 0
            )
            if redeemed_count > 0:
                raise HTTPException(
                    status_code=409, detail={"code": "STATE_CONFLICT", "message": "服务包已核销，不可转赠"}
                )

            # old -> TRANSFERRED
            sp.status = ServicePackageInstanceStatus.TRANSFERRED.value
            for old in entitlements:
                if old.status != EntitlementStatus.TRANSFERRED.value:
                    assert_entitlement_status_transition(current=old.status, target=EntitlementStatus.TRANSFERRED.value)
                old.status = EntitlementStatus.TRANSFERRED.value

            # new instance（ACTIVE）
            new_sp_id = str(uuid4())
            session.add(
                ServicePackageInstance(
                    id=new_sp_id,
                    order_id=sp.order_id,
                    order_item_id=sp.order_item_id,
                    service_package_template_id=sp.service_package_template_id,
                    owner_id=target_user_id,
                    region_scope=sp.region_scope,
                    tier=sp.tier,
                    valid_from=sp.valid_from,
                    valid_until=sp.valid_until,
                    status=ServicePackageInstanceStatus.ACTIVE.value,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

            new_entitlement_ids: list[str] = []
            for old in entitlements:
                new_id = str(uuid4())
                new_voucher_code = _voucher_code_v1()
                new_qr = _qr_payload_v1(entitlement_id=new_id, voucher_code=new_voucher_code)

                session.add(
                    Entitlement(
                        id=new_id,
                        user_id=target_user_id,
                        order_id=old.order_id,
                        entitlement_type=old.entitlement_type,
                        service_type=old.service_type,
                        remaining_count=int(old.remaining_count),
                        total_count=int(old.total_count),
                        valid_from=old.valid_from,
                        valid_until=old.valid_until,
                        applicable_venues=old.applicable_venues,
                        applicable_regions=old.applicable_regions,
                        qr_code=new_qr,
                        voucher_code=new_voucher_code,
                        status=EntitlementStatus.ACTIVE.value,
                        service_package_instance_id=new_sp_id,
                        owner_id=target_user_id,
                        activator_id="",
                        current_user_id=target_user_id,
                        created_at=datetime.utcnow(),
                    )
                )
                new_entitlement_ids.append(new_id)

                session.add(
                    EntitlementTransfer(
                        id=str(uuid4()),
                        entitlement_id=old.id,
                        from_owner_id=e.owner_id,
                        to_owner_id=target_user_id,
                        transferred_at=now,
                    )
                )

            await session.commit()
            data = {"servicePackageInstanceId": new_sp_id, "entitlementIds": new_entitlement_ids}
        else:
            # 按单条权益转赠（保守兜底：即使没有 service_package_instance_id 也可转赠）
            if e.remaining_count != e.total_count:
                raise HTTPException(
                    status_code=409, detail={"code": "STATE_CONFLICT", "message": "权益已使用，不可转赠"}
                )

            redeemed_count = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(RedemptionRecord)
                        .where(
                            RedemptionRecord.entitlement_id == e.id,
                            RedemptionRecord.status == RedemptionStatus.SUCCESS.value,
                        )
                    )
                ).scalar()
                or 0
            )
            if redeemed_count > 0:
                raise HTTPException(
                    status_code=409, detail={"code": "STATE_CONFLICT", "message": "权益已核销，不可转赠"}
                )

            assert_entitlement_status_transition(current=e.status, target=EntitlementStatus.TRANSFERRED.value)
            e.status = EntitlementStatus.TRANSFERRED.value

            new_id = str(uuid4())
            new_voucher_code = _voucher_code_v1()
            new_qr = _qr_payload_v1(entitlement_id=new_id, voucher_code=new_voucher_code)

            session.add(
                Entitlement(
                    id=new_id,
                    user_id=target_user_id,
                    order_id=e.order_id,
                    entitlement_type=e.entitlement_type,
                    service_type=e.service_type,
                    remaining_count=int(e.remaining_count),
                    total_count=int(e.total_count),
                    valid_from=e.valid_from,
                    valid_until=e.valid_until,
                    applicable_venues=e.applicable_venues,
                    applicable_regions=e.applicable_regions,
                    qr_code=new_qr,
                    voucher_code=new_voucher_code,
                    status=EntitlementStatus.ACTIVE.value,
                    service_package_instance_id=None,
                    owner_id=target_user_id,
                    activator_id="",
                    current_user_id=target_user_id,
                    created_at=datetime.utcnow(),
                )
            )
            session.add(
                EntitlementTransfer(
                    id=str(uuid4()),
                    entitlement_id=e.id,
                    from_owner_id=e.owner_id,
                    to_owner_id=target_user_id,
                    transferred_at=now,
                )
            )

            await session.commit()
            data = {"entitlementId": new_id}

    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="transfer_entitlement",
        actor_type=actor_type,
        actor_id=actor_id,
        idempotency_key=f"{id}:{idem_key}",
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )

    return ok(data=data, request_id=request.state.request_id)
