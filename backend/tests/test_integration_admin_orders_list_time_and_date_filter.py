"""集成测试：Admin 订单监管列表的时间口径（样板域）+ dateFrom/dateTo 北京自然日边界。

规格来源（单一真相来源）：
- specs-prod/admin/api-contracts.md#9B.1（时间与时区口径 + dateFrom/dateTo）
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.enums import PaymentMethod, PaymentStatus, ProductFulfillmentType
from app.models.order import Order
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
from app.utils.redis_client import get_redis

pytestmark = pytest.mark.skipif(os.getenv("RUN_INTEGRATION_TESTS") != "1", reason="integration tests disabled")


async def _reset_db_and_redis() -> None:
    r = get_redis()
    await r.flushdb()

    session_factory = get_session_factory()
    async with session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


async def _seed_order(*, created_at_utc_naive: datetime) -> str:
    order_id = str(uuid4())
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Order(
                id=order_id,
                user_id=str(uuid4()),
                order_type="PRODUCT",
                total_amount=10.0,
                payment_method=PaymentMethod.WECHAT.value,
                payment_status=PaymentStatus.PAID.value,
                dealer_id=None,
                dealer_link_id=None,
                fulfillment_type=ProductFulfillmentType.PHYSICAL_GOODS.value,
                fulfillment_status=None,
                goods_amount=10.0,
                shipping_amount=0.0,
                shipping_address_json={"name": "it", "phoneMasked": "138****0000"},
                reservation_expires_at=None,
                shipping_carrier=None,
                shipping_tracking_no=None,
                shipped_at=None,
                delivered_at=None,
                received_at=None,
                created_at=created_at_utc_naive,
                paid_at=created_at_utc_naive,
                confirmed_at=None,
            )
        )
        await session.commit()
    return order_id


def test_admin_orders_list_time_output_is_utc_z_and_date_filter_is_beijing_day():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # 北京时间 2026-01-07 00:00:00 == UTC 2026-01-06 16:00:00
    # - before boundary: UTC 15:59:59 (北京 23:59:59 前一天) -> 不应命中 2026-01-07
    # - at boundary: UTC 16:00:00 (北京 00:00:00 当天) -> 应命中
    # - inside day: UTC 23:00:00 (北京 07:00:00 当天) -> 应命中
    order_before = asyncio.run(_seed_order(created_at_utc_naive=datetime(2026, 1, 6, 15, 59, 59)))
    order_at = asyncio.run(_seed_order(created_at_utc_naive=datetime(2026, 1, 6, 16, 0, 0)))
    order_inside = asyncio.run(_seed_order(created_at_utc_naive=datetime(2026, 1, 6, 23, 0, 0)))

    r = client.get(
        "/api/v1/admin/orders",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"dateFrom": "2026-01-07", "dateTo": "2026-01-07", "page": 1, "pageSize": 50},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True

    ids = {x["id"] for x in (body["data"]["items"] or [])}
    assert order_before not in ids
    assert order_at in ids
    assert order_inside in ids

    # 时间出参：必须是 UTC + Z（样板域约束）
    hit = next(x for x in body["data"]["items"] if x["id"] == order_at)
    assert isinstance(hit.get("createdAt"), str) and hit["createdAt"].endswith("Z")
    assert isinstance(hit.get("paidAt"), str) and hit["paidAt"].endswith("Z")


