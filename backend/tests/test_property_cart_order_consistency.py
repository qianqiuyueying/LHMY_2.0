"""属性测试：购物车和订单管理一致性（属性1）。

规格来源：
- specs/health-services-platform/design.md -> 属性 1：购物车和订单管理一致性
- specs/health-services-platform/tasks.md -> 阶段4-24.4

v1 最小断言：
- 当购物车选中项的 itemType 全部一致时，可推导出一致的 orderType；
- 当 itemType 混合时，应拒绝（v1 不支持混合下单）。
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.models.enums import OrderItemType, OrderType
from app.services.cart_order_rules import CartSelectedItem, infer_order_type_from_cart_items


def _safe_id():
    # UUID-like 文本即可；避免空串
    return st.text(min_size=1, max_size=36)


@given(
    item_type=st.sampled_from([OrderItemType.PRODUCT, OrderItemType.VIRTUAL_VOUCHER]),
    items=st.lists(
        st.tuples(_safe_id(), st.integers(min_value=1, max_value=9999)),
        min_size=1,
        max_size=20,
    ),
)
def test_property_1_cart_to_order_type_infer_ok(item_type: OrderItemType, items: list[tuple[str, int]]):
    cart = [CartSelectedItem(item_type=item_type, item_id=item_id, quantity=qty) for item_id, qty in items]
    order_type = infer_order_type_from_cart_items(items=cart)
    assert order_type == OrderType(item_type.value)


def test_property_1_cart_to_order_type_infer_reject_mixed():
    cart = [
        CartSelectedItem(item_type=OrderItemType.PRODUCT, item_id="p1", quantity=1),
        CartSelectedItem(item_type=OrderItemType.VIRTUAL_VOUCHER, item_id="v1", quantity=1),
    ]
    with pytest.raises(ValueError):
        infer_order_type_from_cart_items(items=cart)

