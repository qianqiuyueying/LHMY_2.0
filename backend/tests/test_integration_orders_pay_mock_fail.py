"""集成测试：订单支付 mock 失败返回（BE-H5-004）。

规格来源：
- specs/health-services-platform/design.md -> POST /api/v1/orders/{id}/pay（200 + FAILED + failureReason）
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.enums import PaymentStatus
from app.models.order import Order
from app.utils.db import get_session_factory
from app.utils.jwt_token import create_user_token
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


def test_orders_pay_mock_fail_returns_failed_business_result():
    asyncio.run(_reset_db_and_redis())

    uid = str(uuid4())
    token = create_user_token(user_id=uid, channel="H5")
    oid = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Order(
                    id=oid,
                    user_id=uid,
                    order_type="SERVICE_PACKAGE",
                    total_amount=100.0,
                    payment_method="WECHAT",
                    payment_status=PaymentStatus.PENDING.value,
                    dealer_id=None,
                    created_at=datetime.utcnow(),
                    paid_at=None,
                    confirmed_at=None,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    r = client.post(
        f"/api/v1/orders/{oid}/pay?mockFail=1",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k1"},
        json={"paymentMethod": "WECHAT"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["paymentStatus"] == "FAILED"
    assert r.json()["data"]["failureReason"]

