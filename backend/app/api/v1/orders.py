"""订单接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> B. C 端核心：`GET/POST /api/v1/orders`、`GET /api/v1/orders/{id}`、`POST /api/v1/orders/{id}/pay`
- specs/health-services-platform/design.md -> API 通用约定（分页/幂等/状态冲突）
- specs/health-services-platform/design.md -> 订单模型（Order/OrderItem）
- specs/health-services-platform/tasks.md -> 阶段4-24/25/26
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import aliased

from app.models.dealer import Dealer
from app.models.enums import (
    DealerStatus,
    OrderItemType,
    OrderType,
    PaymentMethod,
    PaymentStatus,
    ProductFulfillmentType,
    ProductStatus,
)
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User
from app.services.dealer_signing import verify_params
from app.services.idempotency import IdempotencyCachedResult, IdempotencyService
from app.services.order_rules import order_items_match_order_type
from app.services.pricing import resolve_price
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.redis_client import get_redis
from app.utils.response import fail, ok
from app.utils.settings import settings

router = APIRouter(tags=["orders"])


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
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}) from exc


def _user_context_from_authorization(authorization: str | None, *, require_channel: str | None = None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token, require_channel=require_channel)
    return {"actorType": "USER", "userId": str(payload["sub"]), "channel": str(payload.get("channel", ""))}


def _order_item_dto(i: OrderItem) -> dict:
    return {
        "id": i.id,
        "orderId": i.order_id,
        "itemType": i.item_type,
        "itemId": i.item_id,
        "title": i.title,
        "quantity": i.quantity,
        "unitPrice": float(i.unit_price),
        "totalPrice": float(i.total_price),
        "servicePackageTemplateId": i.service_package_template_id,
        "regionScope": i.region_scope,
        "tier": i.tier,
    }


def _order_dto(o: Order, items: list[OrderItem]) -> dict:
    return {
        "id": o.id,
        "userId": o.user_id,
        "orderType": o.order_type,
        "totalAmount": float(o.total_amount),
        "paymentMethod": o.payment_method,
        "paymentStatus": o.payment_status,
        "dealerId": o.dealer_id,
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
    itemType: Literal["PRODUCT", "VIRTUAL_VOUCHER"]
    itemId: str
    quantity: int = Field(..., ge=1, le=9999)


class CreateOrderBody(BaseModel):
    orderType: Literal["PRODUCT", "VIRTUAL_VOUCHER"]
    items: list[CreateOrderItemBody] = Field(..., min_length=1)


@router.post("/orders")
async def create_order(
    request: Request,
    body: CreateOrderBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
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

    # 订单类型校验（小程序不允许 SERVICE_PACKAGE；v1 只允许 PRODUCT/VIRTUAL_VOUCHER）
    try:
        order_type = OrderType(body.orderType)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "orderType 不合法"}) from exc

    if order_type == OrderType.SERVICE_PACKAGE:
        raise HTTPException(status_code=403, detail={"code": "ORDER_TYPE_NOT_ALLOWED", "message": "不允许创建该类型订单"})

    item_types = []
    for it in body.items:
        try:
            item_types.append(OrderItemType(it.itemType))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "itemType 不合法"}) from exc

    if not order_items_match_order_type(order_type, item_types):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "orderType 与 items.itemType 不一致"})

    # v1：H5 下单时支持绑定经销商归属（阶段7-44.3）
    dealer_id_to_bind: str | None = None
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
            raise HTTPException(status_code=403, detail={"code": res.error_code or "DEALER_SIGN_INVALID", "message": "经销商签名校验失败"})
        dealer_id_to_bind = str(dealerId)

    # v1：不引入物流/实物能力
    # - PRODUCT：服务类订单，对应 Product.fulfillmentType=SERVICE
    # - VIRTUAL_VOUCHER：虚拟券订单，对应 Product.fulfillmentType=VIRTUAL_VOUCHER
    required_fulfillment = (
        ProductFulfillmentType.SERVICE.value
        if order_type == OrderType.PRODUCT
        else ProductFulfillmentType.VIRTUAL_VOUCHER.value
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        if dealer_id_to_bind:
            dealer = (await session.scalars(select(Dealer).where(Dealer.id == dealer_id_to_bind).limit(1))).first()
            if dealer is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不存在"})
            if dealer.status != DealerStatus.ACTIVE.value:
                raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "经销商已停用"})

        # 拉取商品并构造订单明细
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

        order_items: list[OrderItem] = []
        total_amount = 0.0
        for it in body.items:
            p = product_map.get(it.itemId)
            if p is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "商品不存在或不可购买"})

            if p.fulfillment_type != required_fulfillment:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "商品类型不匹配"})

            unit_price = float(resolve_price(p.price or {}))
            total_price = unit_price * int(it.quantity)
            total_amount += total_price

            order_items.append(
                OrderItem(
                    id=str(uuid4()),
                    order_id="__PENDING__",
                    item_type=it.itemType,
                    item_id=p.id,
                    title=p.title,
                    quantity=int(it.quantity),
                    unit_price=unit_price,
                    total_price=total_price,
                    service_package_template_id=None,
                    region_scope=None,
                    tier=None,
                )
            )

        o = Order(
            id=str(uuid4()),
            user_id=user_id,
            order_type=order_type.value,
            total_amount=float(total_amount),
            payment_method=PaymentMethod.WECHAT.value,
            payment_status=PaymentStatus.PENDING.value,
            dealer_id=dealer_id_to_bind,
            paid_at=None,
            confirmed_at=None,
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
    orderType: Literal["PRODUCT", "VIRTUAL_VOUCHER", "SERVICE_PACKAGE"] | None = None,
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
        items = (
            await session.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids)))
        ).all()

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
    authorization: str | None = Header(default=None),
    orderNo: str | None = None,
    userId: str | None = None,
    phone: str | None = None,
    orderType: Literal["PRODUCT", "VIRTUAL_VOUCHER", "SERVICE_PACKAGE"] | None = None,
    paymentStatus: Literal["PENDING", "PAID", "FAILED", "REFUNDED"] | None = None,
    dealerId: str | None = None,
    providerId: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    # specs/health-services-platform/design.md -> E-1 admin 订单监管（v1 最小契约）
    await _require_admin(authorization)

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
        .where(OrderItem.item_type.in_([OrderItemType.PRODUCT.value, OrderItemType.VIRTUAL_VOUCHER.value]))
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
                "totalAmount": float(o.total_amount),
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

    return ok(data=_order_dto(o, items), request_id=request.state.request_id)


class PayOrderBody(BaseModel):
    paymentMethod: Literal["WECHAT"]


@router.post("/orders/{id}/pay")
async def pay_order(
    request: Request,
    id: str,
    body: PayOrderBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
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

        # v1：生成 payment 记录（最小字段），并返回小程序调起支付所需参数（mock 口径）
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

    # v1 mock wechatPayParams：为前端联调提供稳定结构；实际对接微信支付需先补齐规格后实现签名/下单。
    now_ts = int(datetime.now(tz=UTC).timestamp())
    wechat_pay_params = {
        "timeStamp": str(now_ts),
        "nonceStr": str(uuid4()).replace("-", ""),
        "package": "prepay_id=mock",
        "signType": "HMAC-SHA256",
        "paySign": "mock",
    }
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

