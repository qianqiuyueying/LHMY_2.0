"""购物车与订单一致性规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 属性 1：购物车和订单管理一致性
- specs/health-services-platform/design.md -> 创建订单规则：orderType 与 items[*].itemType 必须一致
- specs/health-services-platform/tasks.md -> 阶段4-24.4

说明（v1）：
- v1 未定义独立购物车数据模型/接口，本规则以“购物车选中项 == 创建订单请求 items”作为最小落地口径；
- 该规则用于保障：同一批选中项在下单时不会发生类型漂移或结构变形。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import OrderItemType, OrderType
from app.services.order_rules import order_items_match_order_type


@dataclass(frozen=True)
class CartSelectedItem:
    item_type: OrderItemType
    item_id: str
    quantity: int


def infer_order_type_from_cart_items(*, items: list[CartSelectedItem]) -> OrderType:
    """根据购物车选中项推导订单类型（v1：要求所有 itemType 一致）。"""

    if not items:
        raise ValueError("cart items 不能为空")

    # v1：不做“混合下单”
    first = items[0].item_type
    if any(x.item_type != first for x in items):
        raise ValueError("购物车选中项 itemType 必须一致")

    order_type = OrderType(first.value)
    if order_type == OrderType.SERVICE_PACKAGE:
        # v1：小程序不允许创建 SERVICE_PACKAGE（购买入口在 H5）
        raise ValueError("不允许从购物车创建 SERVICE_PACKAGE 订单")

    if not order_items_match_order_type(order_type, [x.item_type for x in items]):
        # 理论上不会发生（因为上面已保证一致），保守兜底
        raise ValueError("orderType 与 items.itemType 不一致")

    return order_type
