"""履约流程路由（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 属性 3：履约流程启动正确性
- specs/health-services-platform/design.md -> Order.orderType 取值与语义说明
- specs/health-services-platform/tasks.md -> 阶段4-25.4

说明（v1）：
- 阶段4只落地“路由决策”这一可测试不变量；
- 具体的履约副作用（生成权益/预约/发券等）在后续阶段按服务域逐步实现并接入该路由。
"""

from __future__ import annotations

from enum import StrEnum

from app.models.enums import OrderType


class FulfillmentFlow(StrEnum):
    """订单支付成功后的履约流程类型（用于路由/后续扩展）。"""

    SERVICE = "SERVICE"
    VOUCHER = "VOUCHER"
    SERVICE_PACKAGE = "SERVICE_PACKAGE"


def resolve_fulfillment_flow(*, order_type: OrderType) -> FulfillmentFlow:
    """根据订单类型解析履约流程类型。"""

    if order_type == OrderType.PRODUCT:
        return FulfillmentFlow.SERVICE
    if order_type == OrderType.VIRTUAL_VOUCHER:
        return FulfillmentFlow.VOUCHER
    if order_type == OrderType.SERVICE_PACKAGE:
        return FulfillmentFlow.SERVICE_PACKAGE
    # StrEnum 理论上不会走到这里；保守兜底
    raise ValueError(f"unsupported order_type: {order_type}")

