"""支付回调处理（v1 最小可执行）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段4-25.3（支付回调处理与状态更新）
- specs/health-services-platform/design.md -> orders.paymentStatus（PENDING/PAID/FAILED/REFUNDED）
- specs/health-services-platform/design.md -> 属性 3：履约流程启动正确性（支付成功后按订单类型路由）

说明（v1）：
- design.md 未定义“微信支付回调”的对外 HTTP 端点契约（URL/签名验签/报文结构等），因此这里仅实现**可复用的回调处理核心逻辑**：
  - 更新 payments/paymentStatus 与 orders/paymentStatus、paidAt
  - 返回履约路由结果，供后续“权益生成/预约/发券”等流程接入
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, update

from app.models.bind_token import BindToken
from app.models.card import Card
from app.models.enums import CardStatus
from app.models.enums import OrderFulfillmentStatus, OrderType, PaymentStatus, ProductFulfillmentType
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.services.order_state_machine import assert_order_status_transition
from app.services.entitlement_generation import generate_entitlements_after_payment_succeeded
from app.services.fulfillment_routing import FulfillmentFlow, resolve_fulfillment_flow
from app.utils.settings import settings


async def mark_payment_succeeded(
    *,
    session,
    order_id: str,
    payment_id: str,
    provider_payload: dict[str, Any] | None = None,
) -> FulfillmentFlow:
    """将支付置为成功，并返回履约流程路由结果。"""

    o = (await session.scalars(select(Order).where(Order.id == order_id).limit(1))).first()
    if o is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})

    p = (
        await session.scalars(select(Payment).where(Payment.id == payment_id, Payment.order_id == order_id).limit(1))
    ).first()
    if p is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "支付记录不存在"})

    if o.payment_status == PaymentStatus.PAID.value:
        # 幂等：重复回调不应报错
        return resolve_fulfillment_flow(order_type=OrderType(o.order_type))

    assert_order_status_transition(current=o.payment_status, target=PaymentStatus.PAID.value)

    now = datetime.now(tz=UTC)
    o.payment_status = PaymentStatus.PAID.value
    o.paid_at = now

    p.payment_status = PaymentStatus.PAID.value
    if provider_payload is not None:
        p.provider_payload = provider_payload

    # v1（h5-anonymous-purchase-bind-token）：
    # - 仅对 SERVICE_PACKAGE 订单生成“未绑定卡（Card）+ 权益（ownerId=cardId）+ bind_token”
    # - Card.id = Order.id（v1 一单一张卡）
    if o.order_type == OrderType.SERVICE_PACKAGE.value:
        card_id = o.id

        # 1) 确保 UNBOUND Card 存在
        card = (await session.scalars(select(Card).where(Card.id == card_id).limit(1))).first()
        if card is None:
            session.add(Card(id=card_id, status=CardStatus.UNBOUND.value, owner_user_id=None))
        else:
            # 若已绑定，则不再生成/刷新 token（避免越权覆盖绑定结果）
            if str(card.status) == CardStatus.BOUND.value:
                await session.commit()
                return resolve_fulfillment_flow(order_type=OrderType(o.order_type))

        # 2) 生成权益：ownerId 临时写 cardId（并写入兼容字段 userId/currentUserId）
        # - 幂等：生成逻辑内部对同一 orderId 做“已生成”检查
        await generate_entitlements_after_payment_succeeded(
            session=session,
            order_id=o.id,
            qr_sign_secret=settings.entitlement_qr_sign_secret,
            owner_id_override=card_id,
        )

        # 3) 生成 bind_token（24h，回调幂等：已有未过期且未使用 token 则复用）
        now2 = datetime.now(tz=UTC)
        existing = (
            await session.scalars(
                select(BindToken)
                .where(
                    BindToken.card_id == card_id,
                    BindToken.used_at.is_(None),
                    BindToken.expires_at > now2.replace(tzinfo=None),
                )
                .limit(1)
            )
        ).first()

        if existing is None:
            # 滚动策略：生成新 token 时作废旧 token（仅 UNBOUND）
            await session.execute(
                update(BindToken)
                .where(BindToken.card_id == card_id, BindToken.used_at.is_(None))
                .values(used_at=now2.replace(tzinfo=None))
            )

            from uuid import uuid4  # noqa: WPS433
            from datetime import timedelta  # noqa: WPS433

            token = uuid4().hex  # 32 chars
            expires_at = (now2 + timedelta(seconds=int(settings.bind_token_expire_seconds))).replace(tzinfo=None)
            session.add(BindToken(token=token, card_id=card_id, expires_at=expires_at, used_at=None))

    # v2：物流商品库存确认扣减（占用 -> 扣减），并进入待发货
    if o.order_type == OrderType.PRODUCT.value and o.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value:
        items: list[OrderItem] = (await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all()
        product_ids = [it.item_id for it in items if it.item_type == "PRODUCT"]
        if product_ids:
            products: list[Product] = (await session.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
            prod_map = {x.id: x for x in products}
            for it in items:
                if it.item_type != "PRODUCT":
                    continue
                p2 = prod_map.get(it.item_id)
                if p2 is None:
                    continue
                qty = int(it.quantity or 0)
                if qty <= 0:
                    continue
                p2.stock = max(0, int(p2.stock or 0) - qty)
                p2.reserved_stock = max(0, int(p2.reserved_stock or 0) - qty)

        o.fulfillment_status = OrderFulfillmentStatus.NOT_SHIPPED.value
        o.reservation_expires_at = None

    await session.commit()

    return resolve_fulfillment_flow(order_type=OrderType(o.order_type))
