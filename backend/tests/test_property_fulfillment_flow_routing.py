"""属性测试：履约流程启动正确性（属性3）。

规格来源：
- specs/health-services-platform/design.md -> 属性 3：履约流程启动正确性
- specs/health-services-platform/tasks.md -> 阶段4-25.4

v1 最小断言：
- 对任意订单类型（PRODUCT/SERVICE_PACKAGE），系统能给出确定的履约流程路由结果。
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.models.enums import OrderType
from app.services.fulfillment_routing import FulfillmentFlow, resolve_fulfillment_flow


@given(st.sampled_from(list(OrderType)))
def test_property_3_fulfillment_flow_routing(order_type: OrderType):
    flow = resolve_fulfillment_flow(order_type=order_type)

    if order_type == OrderType.PRODUCT:
        assert flow == FulfillmentFlow.SERVICE
    elif order_type == OrderType.SERVICE_PACKAGE:
        assert flow == FulfillmentFlow.SERVICE_PACKAGE
    else:
        # StrEnum 理论上不会到这里
        assert False
