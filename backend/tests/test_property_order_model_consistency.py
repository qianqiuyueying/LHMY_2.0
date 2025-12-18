"""属性测试：统一订单模型一致性（属性20）。"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.models.enums import OrderItemType, OrderType
from app.services.order_rules import order_items_match_order_type


@given(
    st.sampled_from(list(OrderType)),
    st.lists(st.sampled_from(list(OrderItemType)), min_size=0, max_size=10),
)
def test_property_20_order_item_type_matches_order_type(order_type: OrderType, item_types: list[OrderItemType]):
    ok = order_items_match_order_type(order_type, item_types)

    # 手工口径：如果存在任意 itemType != orderType，则必须为 False
    manual = all(t.value == order_type.value for t in item_types)
    assert ok == manual
