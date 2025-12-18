"""订单规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 创建订单规则：orderType 与 items[*].itemType 必须一致
- specs/health-services-platform/design.md -> 属性20：统一订单模型一致性

目标：提供可测试的纯规则函数，供后续下单接口复用。
"""

from __future__ import annotations

from app.models.enums import OrderItemType, OrderType


def order_items_match_order_type(order_type: OrderType, item_types: list[OrderItemType]) -> bool:
    """判断订单类型与明细类型是否一致。"""

    return all(t.value == order_type.value for t in item_types)
