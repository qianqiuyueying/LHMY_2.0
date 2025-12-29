"""端到端集成测试：售后仲裁最短链路（v1 最小）。

规格来源：
- specs/功能实现/admin/tasks.md -> T-N13
- specs/health-services-platform/design.md -> 售后/退款与 admin decide 契约

目标：
- USER 创建售后单（UNDER_REVIEW）
- ADMIN 列表可见并裁决（APPROVE）
- 订单进入 REFUNDED（v1 退款模拟）
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.admin import Admin
from app.models.base import Base
from app.models.entitlement import Entitlement
from app.models.enums import EntitlementStatus, EntitlementType, OrderType, PaymentStatus
from app.models.order import Order
from app.models.user import User
from app.services.password_hashing import hash_password
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
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


def test_after_sales_e2e_min_flow_approve_refund():
    asyncio.run(_reset_db_and_redis())

    user_id = str(uuid4())
    admin_id = str(uuid4())
    order_id = str(uuid4())
    entitlement_id = str(uuid4())

    now = datetime.now(tz=UTC).replace(tzinfo=None)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(User(id=user_id, phone="13600000000", nickname="u", identities=[]))
            session.add(
                Admin(
                    id=admin_id,
                    username=f"it_admin_after_sales_e2e_{admin_id[-4:]}",
                    password_hash=hash_password(password="Abcdef!2345"),
                    status="ACTIVE",
                    phone="13800138000",
                )
            )
            session.add(
                Order(
                    id=order_id,
                    user_id=user_id,
                    order_type=OrderType.SERVICE_PACKAGE.value,
                    total_amount=99.0,
                    payment_status=PaymentStatus.PAID.value,
                    paid_at=now,
                )
            )
            session.add(
                Entitlement(
                    id=entitlement_id,
                    user_id=user_id,
                    order_id=order_id,
                    entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                    service_type="DEMO_SERVICE",
                    remaining_count=1,
                    total_count=1,
                    valid_from=now - timedelta(days=1),
                    valid_until=now + timedelta(days=30),
                    applicable_venues=None,
                    applicable_regions=["CITY:110100"],
                    qr_code="DEMO_QR_PAYLOAD",
                    voucher_code="DEMO-VOUCHER-REFUND-1",
                    status=EntitlementStatus.ACTIVE.value,
                    service_package_instance_id=None,
                    owner_id=user_id,
                    activator_id="",
                    current_user_id="",
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    user_token = create_user_token(user_id=user_id, channel="MINI_PROGRAM")
    admin_token, _ = create_admin_token(admin_id=admin_id)

    # 1) USER 创建售后
    r1 = client.post(
        "/api/v1/after-sales",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"orderId": order_id, "type": "REFUND", "reason": "不想要了"},
    )
    assert r1.status_code == 200
    after_sale_id = r1.json()["data"]["id"]
    assert r1.json()["data"]["status"] == "UNDER_REVIEW"

    # 2) ADMIN 列表可见
    r2 = client.get("/api/v1/admin/after-sales", headers={"Authorization": f"Bearer {admin_token}"}, params={"page": 1, "pageSize": 50})
    assert r2.status_code == 200
    ids = [x["id"] for x in r2.json()["data"]["items"]]
    assert after_sale_id in ids

    # 3) ADMIN 裁决同意退款
    r3 = client.put(
        f"/api/v1/admin/after-sales/{after_sale_id}/decide",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE", "decisionNotes": "同意退款（v1）"},
    )
    assert r3.status_code == 200
    assert r3.json()["data"]["status"] == "CLOSED"  # v1：DECIDED -> CLOSED

    # 4) 校验订单进入 REFUNDED
    session_factory = get_session_factory()
    async def _assert_db() -> None:
        async with session_factory() as session:
            o = (await session.get(Order, order_id))
            assert o is not None
            assert o.payment_status == PaymentStatus.REFUNDED.value

            e = (await session.get(Entitlement, entitlement_id))
            assert e is not None
            assert e.status == EntitlementStatus.REFUNDED.value

    asyncio.run(_assert_db())

