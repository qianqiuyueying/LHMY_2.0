"""退款服务（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> B9 售后/退款（after_sales / refunds）
- specs/health-services-platform/design.md -> 订单状态：退款成功 PAID -> REFUNDED
- specs/health-services-platform/design.md -> 属性 4：未核销退款规则
- specs/health-services-platform/tasks.md -> 阶段8-48.1/48.2/48.3

说明（v1）：
- 不对接真实三方支付退款；以“后端最小可执行”的方式模拟退款成功链路：
  - 创建 Refund 记录
  - 更新 Order.payment_status=REFUNDED
  - 更新该订单下 Entitlement.status=REFUNDED
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import func, select, update

from app.models.entitlement import Entitlement
from app.models.enums import EntitlementStatus, OrderType, PaymentStatus, RedemptionStatus, RefundStatus
from app.models.order import Order
from app.models.redemption_record import RedemptionRecord
from app.models.refund import Refund
from app.services.refund_rules import RefundRuleResult, can_refund_unredeemed_virtual_voucher


@dataclass(frozen=True)
class RefundApplyResult:
    ok: bool
    error_code: str | None = None
    refund: Refund | None = None


async def _count_success_redemptions_for_order(*, session, order_id: str) -> int:
    entitlement_ids = (
        await session.scalars(select(Entitlement.id).where(Entitlement.order_id == order_id))
    ).all()
    if not entitlement_ids:
        return 0

    stmt = (
        select(func.count())
        .select_from(RedemptionRecord)
        .where(
            RedemptionRecord.entitlement_id.in_(list(entitlement_ids)),
            RedemptionRecord.status == RedemptionStatus.SUCCESS.value,
        )
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def validate_virtual_voucher_refund_allowed(*, session, order: Order) -> RefundRuleResult:
    if order.order_type != OrderType.VIRTUAL_VOUCHER.value:
        return RefundRuleResult(ok=True, error_code=None)

    redeemed_success_count = await _count_success_redemptions_for_order(session=session, order_id=order.id)
    return can_refund_unredeemed_virtual_voucher(redeemed_success_count=redeemed_success_count)


async def execute_full_refund_for_order(*, session, order: Order, reason: str | None = None) -> RefundApplyResult:
    """执行全额退款（v1）。

    约束：
    - 仅允许对 PAID 订单退款；已退款则幂等返回 SUCCESS 的 refund（若存在）。
    """

    if order.payment_status == PaymentStatus.REFUNDED.value:
        existing = (
            await session.scalars(
                select(Refund)
                .where(Refund.order_id == order.id, Refund.status == RefundStatus.SUCCESS.value)
                .order_by(Refund.created_at.desc())
                .limit(1)
            )
        ).first()
        return RefundApplyResult(ok=True, error_code=None, refund=existing)

    if order.payment_status != PaymentStatus.PAID.value:
        return RefundApplyResult(ok=False, error_code="STATE_CONFLICT", refund=None)

    rule_res = await validate_virtual_voucher_refund_allowed(session=session, order=order)
    if not rule_res.ok:
        return RefundApplyResult(ok=False, error_code=rule_res.error_code or "REFUND_NOT_ALLOWED", refund=None)

    refund = Refund(
        id=str(uuid4()),
        order_id=order.id,
        amount=float(order.total_amount),
        status=RefundStatus.SUCCESS.value,  # v1：最小可执行，直接成功
        reason=(reason.strip() if reason else None),
    )
    session.add(refund)

    # 订单状态更新：PAID -> REFUNDED
    await session.execute(
        update(Order).where(Order.id == order.id).values(payment_status=PaymentStatus.REFUNDED.value)
    )

    # 权益状态更新：ACTIVE -> REFUNDED（v1：不细分 USED/EXPIRED 等；由退款规则确保未核销）
    await session.execute(
        update(Entitlement)
        .where(Entitlement.order_id == order.id)
        .values(status=EntitlementStatus.REFUNDED.value)
    )

    return RefundApplyResult(ok=True, error_code=None, refund=refund)

