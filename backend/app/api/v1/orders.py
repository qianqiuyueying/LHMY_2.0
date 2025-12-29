"""订单接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> B. C 端核心：
  - `GET/POST /api/v1/orders`
  - `GET /api/v1/orders/{id}`
  - `POST /api/v1/orders/{id}/pay`
- specs/health-services-platform/design.md -> API 通用约定（分页/幂等/状态冲突）
- specs/health-services-platform/design.md -> 订单模型（Order/OrderItem）
- specs/health-services-platform/tasks.md -> 阶段4-24/25/26
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import base64
import json
from typing import Literal, Sequence
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import aliased

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.dealer import Dealer
from app.models.enums import (
    DealerStatus,
    AuditAction,
    AuditActorType,
    CommonEnabledStatus,
    OrderItemType,
    OrderType,
    OrderFulfillmentStatus,
    PaymentMethod,
    PaymentStatus,
    ProductFulfillmentType,
    ProductStatus,
)
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.package_service import PackageService
from app.models.payment import Payment
from app.models.product import Product
from app.models.user_address import UserAddress
from app.models.sellable_card import SellableCard
from app.models.service_package import ServicePackage
from app.models.user import User
from app.services.dealer_signing import verify_params
from app.services.idempotency import IdempotencyCachedResult, IdempotencyService
from app.services.order_rules import order_items_match_order_type
from app.services.pricing import resolve_price
from app.services.entitlement_scope_rules import parse_region_scope
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.redis_client import get_redis
from app.utils.response import fail, ok
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token
from app.utils.settings import settings

router = APIRouter(tags=["orders"])


def _mask_tracking_no_last4(no: str | None) -> str | None:
    if not no:
        return None
    s = str(no).strip()
    if len(s) < 4:
        return None
    return s[-4:]


def _sanitize_shipping_address_for_admin(value: object | None) -> dict | None:
    """Admin 场景：不返回收货人姓名/手机号明文/详细地址；最多返回省市区 + phoneMasked（或不返 phone）。"""

    if not isinstance(value, dict):
        return None
    v = value

    receiver_phone = v.get("receiverPhone")
    phone_masked = None
    if isinstance(receiver_phone, str):
        s = receiver_phone.strip()
        if len(s) >= 7:
            phone_masked = f"{s[:3]}****{s[-4:]}"

    out: dict = {
        "countryCode": v.get("countryCode"),
        "provinceCode": v.get("provinceCode"),
        "cityCode": v.get("cityCode"),
        "districtCode": v.get("districtCode"),
    }
    # 允许但不强制返回 phoneMasked
    if phone_masked:
        out["phoneMasked"] = phone_masked
    return out


class ShipOrderBody(BaseModel):
    carrier: str = Field(..., min_length=1, max_length=64)
    trackingNo: str = Field(..., min_length=3, max_length=64)


@router.post("/admin/orders/{id}/ship")
async def admin_ship_order(
    request: Request,
    id: str,
    body: ShipOrderBody,
    admin=Depends(require_admin_phone_bound),
):
    session_factory = get_session_factory()
    async with session_factory() as session:
        o = (await session.scalars(select(Order).where(Order.id == id).limit(1))).first()
        if o is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})

        if o.payment_status != PaymentStatus.PAID.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "仅已支付订单可发货"})
        if o.fulfillment_type != ProductFulfillmentType.PHYSICAL_GOODS.value:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "非物流商品订单不可发货"})

        carrier = body.carrier.strip()
        tracking_no = body.trackingNo.strip()

        # 状态机幂等口径（方案 A）：已 SHIPPED 且运单信息一致 -> 200 no-op；不一致 -> 409 INVALID_STATE_TRANSITION
        if o.fulfillment_status == OrderFulfillmentStatus.SHIPPED.value:
            if (o.shipping_carrier or "").strip() == carrier and (o.shipping_tracking_no or "").strip() == tracking_no:
                items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all()
                return ok(data=_order_dto(o, items), request_id=request.state.request_id)
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "订单已发货，禁止覆盖运单号；请刷新后确认当前状态"},
            )
        if o.fulfillment_status in {OrderFulfillmentStatus.DELIVERED.value, OrderFulfillmentStatus.RECEIVED.value}:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "订单状态已变化，请刷新后重试"},
            )
        if o.fulfillment_status not in {OrderFulfillmentStatus.NOT_SHIPPED.value, None}:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单状态不允许发货"})

        before_status = o.fulfillment_status

        o.shipping_carrier = carrier
        o.shipping_tracking_no = tracking_no
        o.shipped_at = datetime.utcnow()
        o.fulfillment_status = OrderFulfillmentStatus.SHIPPED.value

        # 审计（敏感操作）：运单号不入明文，仅记录后 4 位
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(getattr(admin, "sub", "") or ""),
                action=AuditAction.UPDATE.value,
                resource_type="ORDER",
                resource_id=o.id,
                summary=f"ADMIN 发货：{o.id}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "beforeFulfillmentStatus": before_status,
                    "afterFulfillmentStatus": OrderFulfillmentStatus.SHIPPED.value,
                    "carrier": carrier,
                    "trackingNoLast4": _mask_tracking_no_last4(tracking_no),
                },
            )
        )
        await session.commit()

        items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all()
    return ok(data=_order_dto(o, items), request_id=request.state.request_id)


@router.post("/admin/orders/{id}/deliver")
async def admin_mark_delivered(
    request: Request,
    id: str,
    admin=Depends(require_admin_phone_bound),
):
    session_factory = get_session_factory()
    async with session_factory() as session:
        o = (await session.scalars(select(Order).where(Order.id == id).limit(1))).first()
        if o is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})
        if o.fulfillment_type != ProductFulfillmentType.PHYSICAL_GOODS.value:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "非物流商品订单不可标记妥投"})

        # 幂等口径：已 DELIVERED 再点 -> 200 no-op
        if o.fulfillment_status == OrderFulfillmentStatus.DELIVERED.value:
            items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all()
            return ok(data=_order_dto(o, items), request_id=request.state.request_id)
        # 非法状态迁移：已 RECEIVED 再 deliver -> 409 INVALID_STATE_TRANSITION
        if o.fulfillment_status == OrderFulfillmentStatus.RECEIVED.value:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "订单已签收，禁止标记妥投；请刷新确认当前状态"},
            )
        if o.fulfillment_status != OrderFulfillmentStatus.SHIPPED.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "仅已发货订单可标记妥投"})

        before_status = o.fulfillment_status
        o.fulfillment_status = OrderFulfillmentStatus.DELIVERED.value
        o.delivered_at = datetime.utcnow()

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(getattr(admin, "sub", "") or ""),
                action=AuditAction.UPDATE.value,
                resource_type="ORDER",
                resource_id=o.id,
                summary=f"ADMIN 标记妥投：{o.id}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "beforeFulfillmentStatus": before_status,
                    "afterFulfillmentStatus": OrderFulfillmentStatus.DELIVERED.value,
                },
            )
        )
        await session.commit()
        items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all()
    return ok(data=_order_dto(o, items), request_id=request.state.request_id)


@router.post("/orders/{id}/confirm-received")
async def user_confirm_received(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
):
    user_ctx = _user_context_from_authorization(authorization)
    user_id = user_ctx["userId"]
    session_factory = get_session_factory()
    async with session_factory() as session:
        o = (await session.scalars(select(Order).where(Order.id == id, Order.user_id == user_id).limit(1))).first()
        if o is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})
        if o.fulfillment_type != ProductFulfillmentType.PHYSICAL_GOODS.value:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "非物流商品订单不可确认收货"})
        if o.fulfillment_status not in {OrderFulfillmentStatus.SHIPPED.value, OrderFulfillmentStatus.DELIVERED.value}:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单状态不允许确认收货"})
        o.fulfillment_status = OrderFulfillmentStatus.RECEIVED.value
        o.received_at = datetime.utcnow()
        await session.commit()
        items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all()
    return ok(data=_order_dto(o, items), request_id=request.state.request_id)


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return idempotency_key.strip()


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


async def _require_admin(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_admin_token(token=token)
    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return payload


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


def _parse_dt(raw: str, *, field_name: str) -> datetime:
    try:
        if len(raw) == 10:
            return datetime.fromisoformat(raw + "T00:00:00")
        return datetime.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}
        ) from exc


def _user_context_from_authorization(authorization: str | None, *, require_channel: str | None = None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token, require_channel=require_channel)
    return {"actorType": "USER", "userId": str(payload["sub"]), "channel": str(payload.get("channel", ""))}


def _order_item_dto(i: OrderItem) -> dict:
    parsed = parse_region_scope(i.region_scope or "") if i.region_scope else None
    return {
        "id": i.id,
        "orderId": i.order_id,
        "itemType": i.item_type,
        "itemId": i.item_id,
        "title": i.title,
        "quantity": i.quantity,
        "unitPrice": float(i.unit_price),
        "unitPriceType": str(getattr(i, "unit_price_type", "original") or "original"),
        "totalPrice": float(i.total_price),
        "servicePackageTemplateId": i.service_package_template_id,
        "regionScope": i.region_scope,
        "regionLevel": parsed.level if parsed else None,
        "regionCode": parsed.code if parsed else None,
        "tier": i.tier,
    }


def _order_dto(o: Order, items: Sequence[OrderItem]) -> dict:
    return {
        "id": o.id,
        "userId": o.user_id,
        "orderType": o.order_type,
        "totalAmount": float(o.total_amount),
        "paymentMethod": o.payment_method,
        "paymentStatus": o.payment_status,
        "dealerId": o.dealer_id,
        "dealerLinkId": getattr(o, "dealer_link_id", None),
        # v2：物流商品履约字段（SERVICE 可为空）
        "fulfillmentType": o.fulfillment_type,
        "fulfillmentStatus": o.fulfillment_status,
        "goodsAmount": float(getattr(o, "goods_amount", 0.0) or 0.0),
        "shippingAmount": float(getattr(o, "shipping_amount", 0.0) or 0.0),
        "shippingAddress": getattr(o, "shipping_address_json", None),
        "reservationExpiresAt": (
            o.reservation_expires_at.astimezone().isoformat() if getattr(o, "reservation_expires_at", None) else None
        ),
        "shippingCarrier": getattr(o, "shipping_carrier", None),
        "shippingTrackingNo": getattr(o, "shipping_tracking_no", None),
        "shippedAt": getattr(o, "shipped_at", None).astimezone().isoformat() if getattr(o, "shipped_at", None) else None,
        "deliveredAt": getattr(o, "delivered_at", None).astimezone().isoformat() if getattr(o, "delivered_at", None) else None,
        "receivedAt": getattr(o, "received_at", None).astimezone().isoformat() if getattr(o, "received_at", None) else None,
        "items": [_order_item_dto(x) for x in items],
        "createdAt": o.created_at.astimezone().isoformat(),
        "paidAt": o.paid_at.astimezone().isoformat() if o.paid_at else None,
        "confirmedAt": o.confirmed_at.astimezone().isoformat() if o.confirmed_at else None,
    }


async def _idempotency_replay_if_exists(
    *,
    request: Request,
    operation: str,
    actor_id: str,
    idempotency_key: str,
) -> JSONResponse | None:
    idem = IdempotencyService(get_redis())
    cached = await idem.get(operation=operation, actor_type="USER", actor_id=actor_id, idempotency_key=idempotency_key)
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


class CreateOrderItemBody(BaseModel):
    itemType: Literal["PRODUCT", "SERVICE_PACKAGE"]
    itemId: str
    quantity: int = Field(..., ge=1, le=9999)
    # 仅当 itemType=SERVICE_PACKAGE 时适用（按 design.md 订单明细模型）
    servicePackageTemplateId: str | None = None
    # v2：消费者购买时选择具体区域（regionScope 与 regionLevel/regionCode 二选一即可）
    regionScope: str | None = None
    regionLevel: Literal["CITY", "PROVINCE", "COUNTRY"] | None = None
    regionCode: str | None = None
    # v2：订单明细仍会写入 tier（取模板 tier）；前端无需传
    tier: str | None = None


class CreateOrderBody(BaseModel):
    orderType: Literal["PRODUCT", "SERVICE_PACKAGE"]
    items: list[CreateOrderItemBody] = Field(..., min_length=1)
    # 物流商品 v2：收货地址（可用地址簿 id 或直接传快照）
    shippingAddressId: str | None = None
    shippingAddress: dict | None = None


@router.post("/orders")
async def create_order(
    request: Request,
    body: CreateOrderBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    dealerLinkId: str | None = None,
    dealerId: str | None = None,
    ts: int | None = None,
    nonce: str | None = None,
    sign: str | None = None,
):
    user_ctx = _user_context_from_authorization(authorization)
    user_id = user_ctx["userId"]
    channel = str(user_ctx.get("channel", ""))

    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="create_order",
        actor_id=user_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    # 订单类型校验
    try:
        order_type = OrderType(body.orderType)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "orderType 不合法"}
        ) from exc

    # v1：小程序端不允许创建 SERVICE_PACKAGE（购买入口在 H5）
    if order_type == OrderType.SERVICE_PACKAGE and channel != "H5":
        raise HTTPException(
            status_code=403, detail={"code": "ORDER_TYPE_NOT_ALLOWED", "message": "不允许创建该类型订单"}
        )

    item_types = []
    for it in body.items:
        try:
            item_types.append(OrderItemType(it.itemType))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "itemType 不合法"}
            ) from exc

    if not order_items_match_order_type(order_type, item_types):
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "orderType 与 items.itemType 不一致"}
        )

    # vNext：SERVICE_PACKAGE 下单必须来自 dealerLinkId（长期投放入口，避免 10 分钟签名过期问题）
    # 兼容：旧的 dealerId/ts/nonce/sign 校验能力保留，但不再作为服务包购买主入口参数。
    dealer_link_id = str(dealerLinkId or "").strip() or None
    if dealer_link_id and (dealerId or ts is not None or nonce or sign):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerLinkId 与经销商签名参数不可同时使用"})

    dealer_id_to_bind: str | None = None
    if order_type == OrderType.SERVICE_PACKAGE:
        if channel != "H5":
            raise HTTPException(status_code=403, detail={"code": "ORDER_TYPE_NOT_ALLOWED", "message": "不允许创建该类型订单"})
        if not dealer_link_id:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 dealerLinkId（请使用经销商投放链接打开）"})
    else:
        # PRODUCT 订单仍允许（可选）携带经销商签名参数
        if dealerId or ts is not None or nonce or sign:
            # 必须四者齐全
            if not (dealerId and ts is not None and nonce and sign):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "经销商参数不完整"})
            # 仅 H5 允许携带经销商归属参数
            if channel != "H5":
                raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "仅 H5 下单支持经销商归属"})

            now_ts = int(datetime.now(tz=UTC).timestamp())
            res = verify_params(
                secret=settings.dealer_sign_secret,
                dealer_id=str(dealerId),
                ts=int(ts),
                nonce=str(nonce),
                sign=str(sign),
                now_ts=now_ts,
            )
            if not res.ok:
                raise HTTPException(
                    status_code=403,
                    detail={"code": res.error_code or "DEALER_SIGN_INVALID", "message": "经销商签名校验失败"},
                )
            dealer_id_to_bind = str(dealerId)

    # 说明：
    # - PRODUCT：依赖 Product（供给侧商品/服务/物流商品）
    # - SERVICE_PACKAGE（v2.1）：不依赖 Product，计价载体为 SellableCard（平台售卖配置）

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 用户身份（用于计价）：以后端为准；小程序展示可本地计算，但下单必须用服务端结果落单
        user = (await session.scalars(select(User).where(User.id == user_id).limit(1))).first()
        identities = (user.identities or []) if user is not None else []
        if dealer_link_id:
            # dealerLinkId 绑定经销商（SERVICE_PACKAGE 必走此分支）
            from app.models.dealer_link import DealerLink  # noqa: WPS433
            from app.models.enums import DealerLinkStatus  # noqa: WPS433

            link = (
                await session.scalars(select(DealerLink).where(DealerLink.id == dealer_link_id).limit(1))
            ).first()
            if link is None:
                raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "投放链接不存在"})
            if str(link.status) != DealerLinkStatus.ENABLED.value:
                raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "投放链接不可用"})
            now = datetime.now(tz=UTC)
            if link.valid_from and link.valid_from.replace(tzinfo=None) > now.replace(tzinfo=None):
                raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "投放链接尚未生效"})
            if link.valid_until and link.valid_until.replace(tzinfo=None) < now.replace(tzinfo=None):
                raise HTTPException(status_code=403, detail={"code": "DEALER_LINK_EXPIRED", "message": "投放链接已过期"})

            if not str(link.dealer_id or "").strip():
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "投放链接配置不完整"})

            if order_type == OrderType.SERVICE_PACKAGE:
                # 口径调整：dealerLinkId 代表“经销商入口身份”，不要求该链接本身绑定 sellableCardId。
                # 门禁：用户购买的 sellableCardId 必须存在于该经销商已授权（已生成可用 DealerLink）的卡列表中。
                wanted_ids = {str(it.itemId or "").strip() for it in body.items}
                wanted_ids.discard("")
                if not wanted_ids:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "服务包下单缺少 sellableCardId"})

                allowed_links = (
                    await session.scalars(
                        select(DealerLink).where(
                            DealerLink.dealer_id == str(link.dealer_id),
                            DealerLink.status == DealerLinkStatus.ENABLED.value,
                            DealerLink.sellable_card_id.in_(list(wanted_ids)),
                        )
                    )
                ).all()
                allowed_ids: set[str] = set()
                for l2 in allowed_links:
                    # 兜底过期判断（避免 status 未惰性更新）
                    if l2.valid_from and l2.valid_from.replace(tzinfo=None) > now.replace(tzinfo=None):
                        continue
                    if l2.valid_until and l2.valid_until.replace(tzinfo=None) < now.replace(tzinfo=None):
                        continue
                    sid2 = str(l2.sellable_card_id or "").strip()
                    if sid2:
                        allowed_ids.add(sid2)

                if not wanted_ids.issubset(allowed_ids):
                    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "经销商无权售卖该卡"})

            dealer_id_to_bind = str(link.dealer_id)

        if dealer_id_to_bind:
            dealer = (await session.scalars(select(Dealer).where(Dealer.id == dealer_id_to_bind).limit(1))).first()
            if dealer is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不存在"})
            if dealer.status != DealerStatus.ACTIVE.value:
                raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "经销商已停用"})

        product_map: dict[str, Product] = {}
        sellable_card_map: dict[str, SellableCard] = {}

        # 拉取商品（仅 PRODUCT 需要）
        if order_type == OrderType.PRODUCT:
            product_ids = [x.itemId for x in body.items]
            products = (
                await session.scalars(
                    select(Product).where(
                        Product.id.in_(product_ids),
                        Product.status == ProductStatus.ON_SALE.value,
                    )
                )
            ).all()
            product_map = {p.id: p for p in products}

            # v2：同一笔 PRODUCT 订单不允许混合 SERVICE 与 PHYSICAL_GOODS（先走最小可用闭环）
            ft_set = {str(p.fulfillment_type) for p in products if p is not None and str(p.fulfillment_type)}
            if len(ft_set) > 1:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "同一订单不允许混合服务与物流商品"})
            product_fulfillment = (list(ft_set)[0] if ft_set else ProductFulfillmentType.SERVICE.value)
            if product_fulfillment not in {ProductFulfillmentType.SERVICE.value, ProductFulfillmentType.PHYSICAL_GOODS.value}:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "商品履约类型不合法"})
        else:
            product_fulfillment = ProductFulfillmentType.SERVICE.value

        # v2：物流商品下单必须带收货地址（会写入订单快照）
        shipping_snapshot: dict | None = None
        if order_type == OrderType.PRODUCT and product_fulfillment == ProductFulfillmentType.PHYSICAL_GOODS.value:
            addr_id = str(body.shippingAddressId or "").strip()
            raw_addr = body.shippingAddress if isinstance(body.shippingAddress, dict) else None
            if not addr_id and not raw_addr:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "物流商品下单必须选择收货地址"})

            if addr_id:
                a = (
                    await session.scalars(
                        select(UserAddress).where(UserAddress.id == addr_id, UserAddress.user_id == user_id).limit(1)
                    )
                ).first()
                if a is None:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "收货地址不存在"})
                shipping_snapshot = {
                    "addressId": a.id,
                    "receiverName": a.receiver_name,
                    "receiverPhone": a.receiver_phone,
                    "countryCode": a.country_code,
                    "provinceCode": a.province_code,
                    "cityCode": a.city_code,
                    "districtCode": a.district_code,
                    "addressLine": a.address_line,
                    "postalCode": a.postal_code,
                }
            else:
                shipping_snapshot = {
                    "addressId": None,
                    "receiverName": str(raw_addr.get("receiverName") or "").strip(),
                    "receiverPhone": str(raw_addr.get("receiverPhone") or "").strip(),
                    "countryCode": str(raw_addr.get("countryCode") or "").strip() or None,
                    "provinceCode": str(raw_addr.get("provinceCode") or "").strip() or None,
                    "cityCode": str(raw_addr.get("cityCode") or "").strip() or None,
                    "districtCode": str(raw_addr.get("districtCode") or "").strip() or None,
                    "addressLine": str(raw_addr.get("addressLine") or "").strip(),
                    "postalCode": str(raw_addr.get("postalCode") or "").strip() or None,
                }
                if not shipping_snapshot.get("receiverName") or not shipping_snapshot.get("receiverPhone") or not shipping_snapshot.get("addressLine"):
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "收货地址信息不完整"})

        # 拉取可售卡（仅 SERVICE_PACKAGE 需要）
        if order_type == OrderType.SERVICE_PACKAGE:
            sellable_card_ids = list({str(x.itemId).strip() for x in body.items if str(x.itemId).strip()})
            if not sellable_card_ids:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "服务包下单缺少 sellableCardId"})
            cards = (await session.scalars(select(SellableCard).where(SellableCard.id.in_(sellable_card_ids)))).all()
            sellable_card_map = {c.id: c for c in cards}

        # 预取服务包模板（仅 SERVICE_PACKAGE 使用）
        service_package_templates: dict[str, ServicePackage] = {}
        if order_type == OrderType.SERVICE_PACKAGE:
            template_ids = list(
                {(x.servicePackageTemplateId or "").strip() for x in body.items if x.servicePackageTemplateId}
            )
            if not template_ids:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "INVALID_ARGUMENT", "message": "服务包下单缺少 servicePackageTemplateId"},
                )
            templates = (await session.scalars(select(ServicePackage).where(ServicePackage.id.in_(template_ids)))).all()
            service_package_templates = {t.id: t for t in templates}

        order_items: list[OrderItem] = []
        goods_amount = 0.0
        shipping_amount = 0.0
        for it in body.items:
            sp_template_id: str | None = None
            region_scope: str | None = None
            tier: str | None = None
            title: str = ""
            biz_item_id: str = ""

            if order_type == OrderType.SERVICE_PACKAGE:
                # v2.1：itemId 即 sellableCardId
                biz_item_id = str(it.itemId).strip()
                sc = sellable_card_map.get(biz_item_id)
                if sc is None:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "可售卡不存在或不可购买"})
                if sc.status != CommonEnabledStatus.ENABLED.value:
                    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "可售卡已停用"})

                title = sc.name
                sp_template_id = (it.servicePackageTemplateId or "").strip() or None
                region_scope = (it.regionScope or "").strip() or None
                if not region_scope:
                    rl = (str(it.regionLevel or "")).strip().upper() or None
                    rc = (str(it.regionCode or "")).strip() or None
                    if not rl:
                        raise HTTPException(
                            status_code=400,
                            detail={"code": "INVALID_ARGUMENT", "message": "服务包明细缺少 regionLevel/regionCode"},
                        )
                    if rl not in {"CITY", "PROVINCE", "COUNTRY"}:
                        raise HTTPException(
                            status_code=400,
                            detail={"code": "INVALID_ARGUMENT", "message": "regionLevel 不合法"},
                        )
                    if rl == "COUNTRY":
                        rc = rc or "CN"
                    if not rc:
                        raise HTTPException(
                            status_code=400,
                            detail={"code": "INVALID_ARGUMENT", "message": "服务包明细缺少 regionCode"},
                        )
                    region_scope = f"{rl}:{rc}"

                if not sp_template_id or not region_scope:
                    raise HTTPException(
                        status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "服务包明细缺少必要参数"}
                    )

                template = service_package_templates.get(sp_template_id)
                if template is None:
                    raise HTTPException(
                        status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "服务包模板不存在"}
                    )

                # v2.1：可售卡区域级别必须与模板一致
                if str(sc.region_level).strip().upper() != str(template.region_level).strip().upper():
                    raise HTTPException(
                        status_code=400,
                        detail={"code": "INVALID_ARGUMENT", "message": "可售卡区域级别与模板不一致"},
                    )

                parsed = parse_region_scope(region_scope)
                if parsed is None:
                    raise HTTPException(
                        status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "regionScope 不合法"}
                    )
                if str(parsed.level).upper() != str(template.region_level).upper():
                    raise HTTPException(
                        status_code=400,
                        detail={"code": "INVALID_ARGUMENT", "message": "regionScope 与模板区域级别不一致"},
                    )

                # v2：tier 仅作为模板属性存储（不作为计价维度）；统一取模板 tier
                tier = str(template.tier)

                # 兜底：确保模板已配置“服务类目×次数”（避免支付成功后才失败）
                ps_count = int(
                    (
                        await session.execute(
                            select(func.count())
                            .select_from(PackageService)
                            .where(PackageService.service_package_id == sp_template_id)
                        )
                    ).scalar()
                    or 0
                )
                if ps_count <= 0:
                    raise HTTPException(
                        status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "服务包模板未配置服务类别×次数"}
                    )

            # 计价：
            # - PRODUCT：走商品 price（含员工/会员/活动裁决）
            # - SERVICE_PACKAGE（v2.1）：走 SellableCard.price_original（唯一售价）
            unit_price = 0.0
            if order_type == OrderType.SERVICE_PACKAGE:
                try:
                    unit_price = float(sc.price_original or 0)  # type: ignore[name-defined]
                except Exception as exc:  # noqa: BLE001
                    raise HTTPException(
                        status_code=400,
                        detail={"code": "INVALID_ARGUMENT", "message": "可售卡售价不合法（priceOriginal 必填且 >= 0）"},
                    ) from exc
            else:
                p = product_map.get(it.itemId)
                if p is None:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "商品不存在或不可购买"})
                if str(p.fulfillment_type) != str(product_fulfillment):
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "商品类型不匹配"})
                # v2：物流商品库存占用
                if product_fulfillment == ProductFulfillmentType.PHYSICAL_GOODS.value:
                    available = int(p.stock or 0) - int(p.reserved_stock or 0)
                    if available < int(it.quantity):
                        raise HTTPException(status_code=409, detail={"code": "OUT_OF_STOCK", "message": "库存不足"})
                    p.reserved_stock = int(p.reserved_stock or 0) + int(it.quantity)
                title = p.title
                biz_item_id = p.id
                unit_price, unit_price_type = resolve_price(p.price or {}, identities=identities)

            total_price = unit_price * int(it.quantity)
            goods_amount += total_price
            if order_type == OrderType.PRODUCT and product_fulfillment == ProductFulfillmentType.PHYSICAL_GOODS.value:
                shipping_amount += float(p.shipping_fee or 0.0) * int(it.quantity)  # type: ignore[name-defined]

            order_items.append(
                OrderItem(
                    id=str(uuid4()),
                    order_id="__PENDING__",
                    item_type=it.itemType,
                    item_id=biz_item_id,
                    title=title,
                    quantity=int(it.quantity),
                    unit_price=unit_price,
                    unit_price_type=(unit_price_type if order_type == OrderType.PRODUCT else "original"),
                    total_price=total_price,
                    service_package_template_id=sp_template_id,
                    region_scope=region_scope,
                    tier=tier,
                )
            )

        total_amount = float(goods_amount + shipping_amount) if order_type == OrderType.PRODUCT else float(goods_amount)
        if order_type == OrderType.SERVICE_PACKAGE:
            total_amount = float(goods_amount)

        reservation_expires_at = None
        if order_type == OrderType.PRODUCT and product_fulfillment == ProductFulfillmentType.PHYSICAL_GOODS.value:
            reservation_expires_at = datetime.utcnow() + timedelta(seconds=int(settings.order_payment_timeout_seconds or 900))

        o = Order(
            id=str(uuid4()),
            user_id=user_id,
            order_type=order_type.value,
            total_amount=float(total_amount),
            payment_method=PaymentMethod.WECHAT.value,
            payment_status=PaymentStatus.PENDING.value,
            dealer_id=dealer_id_to_bind,
            dealer_link_id=dealer_link_id,
            paid_at=None,
            confirmed_at=None,
            fulfillment_type=(product_fulfillment if order_type == OrderType.PRODUCT else None),
            fulfillment_status=(
                OrderFulfillmentStatus.NOT_SHIPPED.value
                if order_type == OrderType.PRODUCT and product_fulfillment == ProductFulfillmentType.PHYSICAL_GOODS.value
                else None
            ),
            goods_amount=float(goods_amount),
            shipping_amount=float(shipping_amount),
            shipping_address_json=shipping_snapshot,
            reservation_expires_at=reservation_expires_at,
        )
        session.add(o)
        await session.flush()

        for oi in order_items:
            oi.order_id = o.id
            session.add(oi)

        await session.commit()

    data = _order_dto(o, order_items)

    # 幂等写回：仅缓存“已产生副作用”的结果
    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="create_order",
        actor_type="USER",
        actor_id=user_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )

    return ok(data=data, request_id=request.state.request_id)


@router.get("/orders")
async def list_orders(
    request: Request,
    authorization: str | None = Header(default=None),
    status: Literal["PENDING", "PAID", "FAILED", "REFUNDED"] | None = None,
    orderType: Literal["PRODUCT", "SERVICE_PACKAGE"] | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    user_ctx = _user_context_from_authorization(authorization)
    user_id = user_ctx["userId"]

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Order).where(Order.user_id == user_id)
    if status:
        stmt = stmt.where(Order.payment_status == status)
    if orderType:
        stmt = stmt.where(Order.order_type == orderType)
    stmt = stmt.order_by(Order.created_at.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        orders = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

        # v1：Order 接口返回 items，按订单批量查询
        order_ids = [o.id for o in orders]
        items = (await session.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids)))).all()

    items_by_order: dict[str, list[OrderItem]] = {}
    for it in items:
        items_by_order.setdefault(it.order_id, []).append(it)

    return ok(
        data={
            "items": [_order_dto(o, items_by_order.get(o.id, [])) for o in orders],
            "page": page,
            "pageSize": page_size,
            "total": total,
        },
        request_id=request.state.request_id,
    )


@router.get("/admin/orders")
async def admin_list_orders(
    request: Request,
    _admin=Depends(require_admin),
    orderNo: str | None = None,
    userId: str | None = None,
    phone: str | None = None,
    orderType: Literal["PRODUCT", "SERVICE_PACKAGE"] | None = None,
    fulfillmentType: Literal["SERVICE", "PHYSICAL_GOODS"] | None = None,
    paymentStatus: Literal["PENDING", "PAID", "FAILED", "REFUNDED"] | None = None,
    dealerId: str | None = None,
    providerId: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    # specs/health-services-platform/design.md -> E-1 admin 订单监管（v1 最小契约）
    # 权限：仅 ADMIN（由 require_admin 负责 401/403）

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    u = aliased(User)

    # providerId 推导：从订单明细关联商品。若同一订单存在多个 provider，则 providerId 置空。
    provider_agg = (
        select(
            OrderItem.order_id.label("order_id"),
            func.min(Product.provider_id).label("min_provider_id"),
            func.max(Product.provider_id).label("max_provider_id"),
        )
        .select_from(OrderItem)
        .join(Product, Product.id == OrderItem.item_id, isouter=True)
        .where(OrderItem.item_type.in_([OrderItemType.PRODUCT.value]))
        .group_by(OrderItem.order_id)
        .subquery()
    )

    provider_id_expr = case(
        (provider_agg.c.min_provider_id == provider_agg.c.max_provider_id, provider_agg.c.min_provider_id),
        else_=None,
    ).label("provider_id")

    stmt = (
        select(Order, u.phone, provider_id_expr)
        .join(u, u.id == Order.user_id, isouter=True)
        .join(provider_agg, provider_agg.c.order_id == Order.id, isouter=True)
    )

    if orderNo and orderNo.strip():
        stmt = stmt.where(Order.id == orderNo.strip())
    if userId and userId.strip():
        stmt = stmt.where(Order.user_id == userId.strip())
    if phone and phone.strip():
        stmt = stmt.where(u.phone.like(f"%{phone.strip()}%"))
    if orderType:
        stmt = stmt.where(Order.order_type == str(orderType))
    if fulfillmentType:
        stmt = stmt.where(Order.fulfillment_type == str(fulfillmentType))
    if paymentStatus:
        stmt = stmt.where(Order.payment_status == str(paymentStatus))
    if dealerId and dealerId.strip():
        stmt = stmt.where(Order.dealer_id == dealerId.strip())
    if providerId and providerId.strip():
        stmt = stmt.where(provider_id_expr == providerId.strip())

    if dateFrom:
        stmt = stmt.where(Order.created_at >= _parse_dt(str(dateFrom), field_name="dateFrom"))
    if dateTo:
        stmt = stmt.where(Order.created_at <= _parse_dt(str(dateTo), field_name="dateTo"))

    stmt = stmt.order_by(Order.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items: list[dict] = []
    for o, buyer_phone, provider_id in rows:
        items.append(
            {
                "id": o.id,
                "orderNo": o.id,  # spec：v1 口径 orderNo=id
                "userId": o.user_id,
                "buyerPhoneMasked": _mask_phone(buyer_phone),
                "orderType": o.order_type,
                "paymentStatus": o.payment_status,
                "fulfillmentType": o.fulfillment_type,
                "fulfillmentStatus": o.fulfillment_status,
                "totalAmount": float(o.total_amount),
                "goodsAmount": float(getattr(o, "goods_amount", 0.0) or 0.0),
                "shippingAmount": float(getattr(o, "shipping_amount", 0.0) or 0.0),
                "shippingCarrier": getattr(o, "shipping_carrier", None),
                # 规格（TASK-P0-006）：Admin 不出运单号明文，仅 last4
                "trackingNoLast4": _mask_tracking_no_last4(getattr(o, "shipping_tracking_no", None)),
                "shippedAt": getattr(o, "shipped_at", None).astimezone().isoformat() if getattr(o, "shipped_at", None) else None,
                "dealerId": o.dealer_id,
                "providerId": provider_id,
                "createdAt": o.created_at.astimezone().isoformat(),
                "paidAt": o.paid_at.astimezone().isoformat() if o.paid_at else None,
            }
        )

    return ok(
        data={"items": items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.get("/orders/{id}")
async def get_order_detail(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
):
    # v1：支持 USER（本人）或 ADMIN（全量）。DEALER/PROVIDER 延后到对应账号体系阶段落地。
    admin_ctx = await _try_get_admin_context(authorization)
    user_ctx = None if admin_ctx else _user_context_from_authorization(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(Order).where(Order.id == id).limit(1)
        if user_ctx:
            stmt = stmt.where(Order.user_id == user_ctx["userId"])
        o = (await session.scalars(stmt)).first()
        if o is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})

        items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all()

    data = _order_dto(o, items)
    # 规格（TASK-P0-006）：Admin 场景不返回运单号/收货地址明文
    if admin_ctx is not None:
        data.pop("shippingTrackingNo", None)
        data["trackingNoLast4"] = _mask_tracking_no_last4(getattr(o, "shipping_tracking_no", None))
        data["shippingAddress"] = _sanitize_shipping_address_for_admin(getattr(o, "shipping_address_json", None))
    return ok(data=data, request_id=request.state.request_id)


class PayOrderBody(BaseModel):
    paymentMethod: Literal["WECHAT"]

def _load_wechatpay_mch_private_key_pem() -> bytes:
    raw = (settings.wechat_pay_mch_private_key_pem_or_path or "").strip()
    if not raw:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PAYMENT_NOT_CONFIGURED",
                "message": "微信支付未配置：缺少商户私钥（WECHAT_PAY_MCH_PRIVATE_KEY_PEM_OR_PATH）",
            },
        )

    if raw.startswith("-----BEGIN"):
        return raw.encode("utf-8")

    try:
        with open(raw, "rb") as f:  # noqa: PTH123
            return f.read()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail={"code": "PAYMENT_NOT_CONFIGURED", "message": "微信支付配置无效：无法读取商户私钥文件"},
        ) from exc


def _wechatpay_sign_rsa_sha256(*, message: str) -> str:
    key = load_pem_private_key(_load_wechatpay_mch_private_key_pem(), password=None)
    sig = key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode("utf-8")


def _wechatpay_build_authorization(*, method: str, canonical_url: str, body_json: str) -> tuple[str, str, str]:
    mchid = (settings.wechat_pay_mch_id or "").strip()
    serial_no = (settings.wechat_pay_mch_cert_serial or "").strip()
    if not mchid or not serial_no:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PAYMENT_NOT_CONFIGURED",
                "message": "微信支付未配置：缺少商户号/商户证书序列号（WECHAT_PAY_MCH_ID/WECHAT_PAY_MCH_CERT_SERIAL）",
            },
        )

    ts = str(int(datetime.now(tz=UTC).timestamp()))
    nonce = str(uuid4()).replace("-", "")
    message = f"{method}\n{canonical_url}\n{ts}\n{nonce}\n{body_json}\n"
    signature = _wechatpay_sign_rsa_sha256(message=message)
    auth = (
        'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{mchid}",nonce_str="{nonce}",timestamp="{ts}",serial_no="{serial_no}",signature="{signature}"'
    )
    return auth, ts, nonce


async def _wechatpay_jsapi_prepay(*, order_id: str, amount: float, openid: str) -> dict:
    appid = (settings.wechat_pay_appid or "").strip()
    notify_url = (settings.wechat_pay_notify_url or "").strip()
    base_url = (settings.wechat_pay_gateway_base_url or "").strip() or "https://api.mch.weixin.qq.com"
    mchid = (settings.wechat_pay_mch_id or "").strip()
    if not appid or not notify_url or not mchid:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PAYMENT_NOT_CONFIGURED",
                "message": "微信支付未配置：缺少 APPID/回调地址/商户号（WECHAT_PAY_APPID/WECHAT_PAY_NOTIFY_URL/WECHAT_PAY_MCH_ID）",
            },
        )

    payload = {
        "appid": appid,
        "mchid": mchid,
        "description": f"LHMY Order {order_id[:8]}",
        "out_trade_no": order_id,
        "notify_url": notify_url,
        "amount": {"total": int(round(float(amount) * 100)), "currency": "CNY"},
        "payer": {"openid": openid},
    }
    body_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    canonical_url = "/v3/pay/transactions/jsapi"
    auth, _ts, _nonce = _wechatpay_build_authorization(method="POST", canonical_url=canonical_url, body_json=body_json)

    headers = {
        "Authorization": auth,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "LHMY/mini-program-pay",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, base_url=base_url) as client:
            r = await client.post(canonical_url, content=body_json.encode("utf-8"), headers=headers)
            data = r.json() if r.content else {}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "failureReason": "微信支付网络请求失败", "raw": {"error": str(exc)}}

    if r.status_code not in (200, 201) or not isinstance(data, dict) or not data.get("prepay_id"):
        msg = str(data.get("message") or data.get("detail") or "") if isinstance(data, dict) else ""
        return {"ok": False, "failureReason": msg or "微信支付下单失败", "raw": data}
    return {"ok": True, "prepayId": str(data["prepay_id"]), "raw": data}


def _wechatpay_build_jsapi_pay_params(*, prepay_id: str) -> dict:
    appid = (settings.wechat_pay_appid or "").strip()
    time_stamp = str(int(datetime.now(tz=UTC).timestamp()))
    nonce_str = str(uuid4()).replace("-", "")
    package = f"prepay_id={prepay_id}"
    message = f"{appid}\n{time_stamp}\n{nonce_str}\n{package}\n"
    pay_sign = _wechatpay_sign_rsa_sha256(message=message)
    return {
        "timeStamp": time_stamp,
        "nonceStr": nonce_str,
        "package": package,
        "signType": "RSA",
        "paySign": pay_sign,
    }


@router.post("/orders/{id}/pay")
async def pay_order(
    request: Request,
    id: str,
    body: PayOrderBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    mockFail: int | None = None,
):
    user_ctx = _user_context_from_authorization(authorization)
    user_id = user_ctx["userId"]

    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="pay_order",
        actor_id=user_id,
        idempotency_key=f"{id}:{idem_key}",
    )
    if replay is not None:
        return replay

    if body.paymentMethod != PaymentMethod.WECHAT.value:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "paymentMethod 不支持"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        o = (await session.scalars(select(Order).where(Order.id == id, Order.user_id == user_id).limit(1))).first()
        if o is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})

        if o.payment_status != PaymentStatus.PENDING.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单状态不允许支付"})

        # v1：生成 payment 记录（最小字段）
        #
        # v1 mock 支付失败（仅联调/回归）：允许通过 query mockFail=1 稳定触发失败结果，
        # 且不改变 orders.payment_status（保持 PENDING 便于“重新支付”）。
        if mockFail == 1 and str(settings.app_env).lower() != "production":
            payment = Payment(
                id=str(uuid4()),
                order_id=o.id,
                payment_method=PaymentMethod.WECHAT.value,
                payment_status=PaymentStatus.FAILED.value,
                amount=float(o.total_amount),
                provider_payload={"failureReason": "MOCK_PAYMENT_FAILED"},
            )
            session.add(payment)
            await session.commit()

            data = {
                "orderId": o.id,
                "paymentStatus": PaymentStatus.FAILED.value,
                "failureReason": "MOCK_PAYMENT_FAILED",
            }
            idem = IdempotencyService(get_redis())
            await idem.set(
                operation="pay_order",
                actor_type="USER",
                actor_id=user_id,
                idempotency_key=f"{id}:{idem_key}",
                result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
            )
            return ok(data=data, request_id=request.state.request_id)

        # v1：返回小程序调起支付所需参数（mock 口径）；实际对接微信支付需先补齐规格后实现签名/下单。
        payment = Payment(
            id=str(uuid4()),
            order_id=o.id,
            payment_method=PaymentMethod.WECHAT.value,
            payment_status=PaymentStatus.PENDING.value,
            amount=float(o.total_amount),
            provider_payload=None,
        )
        session.add(payment)
        await session.commit()

    # v1：真实微信支付 JSAPI 预支付
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(User).where(User.id == user_id).limit(1))).first()
        openid = str(u.openid or "").strip() if u else ""

    if not openid:
        data = {
            "orderId": o.id,
            "paymentStatus": PaymentStatus.FAILED.value,
            "failureReason": "未获取到openid，请重新登录后重试",
        }
    else:
        prepay = await _wechatpay_jsapi_prepay(order_id=o.id, amount=float(o.total_amount), openid=openid)
        if not prepay.get("ok"):
            data = {
                "orderId": o.id,
                "paymentStatus": PaymentStatus.FAILED.value,
                "failureReason": str(prepay.get("failureReason") or "微信支付下单失败"),
            }
        else:
            wechat_pay_params = _wechatpay_build_jsapi_pay_params(prepay_id=str(prepay["prepayId"]))
            data = {
                "orderId": o.id,
                "paymentStatus": PaymentStatus.PENDING.value,
                "wechatPayParams": wechat_pay_params,
            }

    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="pay_order",
        actor_type="USER",
        actor_id=user_id,
        idempotency_key=f"{id}:{idem_key}",
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )

    return ok(data=data, request_id=request.state.request_id)
