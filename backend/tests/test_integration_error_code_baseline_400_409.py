"""集成测试：统一错误码基线（TASK-P0-007，补齐 400/409 覆盖）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#7 错误码与语义（最小集合 + 前端动作）
- specs-prod/admin/tasks.md#TASK-P0-007

覆盖范围（最小）：
- 400 INVALID_ARGUMENT：参数校验失败（admin bookings 非法日期）
- 409 INVALID_STATE_TRANSITION：状态机非法迁移（admin deliver：RECEIVED 再 deliver）
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
from app.models.enums import OrderFulfillmentStatus, OrderType, PaymentMethod, PaymentStatus, ProductFulfillmentType
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


def _assert_fail_envelope(resp_json: dict, *, code: str) -> None:
    assert resp_json.get("success") is False
    assert resp_json.get("data") is None
    assert resp_json.get("error", {}).get("code") == code
    assert isinstance(resp_json.get("error", {}).get("message"), str)
    assert isinstance(resp_json.get("requestId"), str)


def test_400_invalid_argument_admin_bookings_invalid_date():
    asyncio.run(_reset_db_and_redis())
    admin_token, _jti = create_admin_token(admin_id="00000000-0000-0000-0000-00000000a001")
    client = TestClient(app)

    r = client.get(
        "/api/v1/admin/bookings",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"dateFrom": "2025-13-01", "page": 1, "pageSize": 20},
    )
    assert r.status_code == 400
    _assert_fail_envelope(r.json(), code="INVALID_ARGUMENT")


def test_409_invalid_state_transition_admin_deliver_when_received():
    asyncio.run(_reset_db_and_redis())
    admin_token, _jti = create_admin_token(admin_id="00000000-0000-0000-0000-00000000a001")
    client = TestClient(app)

    order_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Order(
                    id=order_id,
                    user_id=str(uuid4()),
                    order_type=OrderType.PRODUCT.value,
                    total_amount=88.0,
                    payment_method=PaymentMethod.WECHAT.value,
                    payment_status=PaymentStatus.PAID.value,
                    dealer_id=None,
                    dealer_link_id=None,
                    fulfillment_type=ProductFulfillmentType.PHYSICAL_GOODS.value,
                    fulfillment_status=OrderFulfillmentStatus.RECEIVED.value,  # 已签收
                    goods_amount=88.0,
                    shipping_amount=0.0,
                    shipping_address_json=None,
                    reservation_expires_at=None,
                    shipping_carrier="SF",
                    shipping_tracking_no="SF0000",
                    shipped_at=now,
                    delivered_at=now,
                    received_at=now,
                    created_at=now,
                    paid_at=now,
                    confirmed_at=None,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    r = client.post(
        f"/api/v1/admin/orders/{order_id}/deliver",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": uuid4().hex},
        json={},  # body 不需要
    )
    assert r.status_code == 409
    _assert_fail_envelope(r.json(), code="INVALID_STATE_TRANSITION")


