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
from sqlalchemy import select

from app.models.enums import OrderType, PaymentStatus
from app.models.order import Order
from app.models.payment import Payment
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

    p = (await session.scalars(select(Payment).where(Payment.id == payment_id, Payment.order_id == order_id).limit(1))).first()
    if p is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "支付记录不存在"})

    if o.payment_status == PaymentStatus.PAID.value:
        # 幂等：重复回调不应报错
        return resolve_fulfillment_flow(order_type=OrderType(o.order_type))

    if o.payment_status != PaymentStatus.PENDING.value:
        raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单状态不允许置为支付成功"})

    now = datetime.now(tz=UTC)
    o.payment_status = PaymentStatus.PAID.value
    o.paid_at = now

    p.payment_status = PaymentStatus.PAID.value
    if provider_payload is not None:
        p.provider_payload = provider_payload

    # 阶段5：支付成功后自动生成权益（虚拟券/服务包）
    # - 幂等：生成逻辑内部对同一 orderId 做“已生成”检查
    await generate_entitlements_after_payment_succeeded(
        session=session,
        order_id=o.id,
        qr_sign_secret=settings.entitlement_qr_sign_secret,
    )

    await session.commit()

    return resolve_fulfillment_flow(order_type=OrderType(o.order_type))

