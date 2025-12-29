"""订单状态机（REQ-P1-004）。

规格来源：
- specs/health-services-platform/后端升级需求与变更清单（v1）.md -> REQ-P1-004
- specs/health-services-platform/design.md -> B2 订单支付（orders.paymentStatus）
"""

from __future__ import annotations

from fastapi import HTTPException

from app.models.enums import PaymentStatus


_ALLOWED: dict[str, set[str]] = {
    PaymentStatus.PENDING.value: {PaymentStatus.PAID.value, PaymentStatus.FAILED.value},
    PaymentStatus.PAID.value: {PaymentStatus.REFUNDED.value},
    PaymentStatus.FAILED.value: set(),
    PaymentStatus.REFUNDED.value: set(),
}


def assert_order_status_transition(*, current: str, target: str) -> None:
    allowed = _ALLOWED.get(str(current), set())
    if str(target) not in allowed:
        raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单状态不允许变更"})


def can_transition(*, current: str, target: str) -> bool:
    return str(target) in _ALLOWED.get(str(current), set())

