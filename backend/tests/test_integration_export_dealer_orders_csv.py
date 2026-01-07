"""集成测试：导出（Dealer Orders CSV）生产化基线（Batch4）。

规格来源（单一真相来源）：
- specs-prod/admin/security.md#5 导出安全（v1：同步直下，不落盘 TTL=0）
- specs-prod/admin/api-contracts.md#10(9)（你已拍板：dateFrom/dateTo 必填；maxRows=5000）
- specs-prod/admin/tasks.md#TASK-P0-003
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.models  # noqa: F401
from app.main import app
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.order import Order
from app.services.password_hashing import hash_password
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


def test_export_requires_date_from_to_and_audited_and_csv_attachment():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # FLOW-ACCOUNTS 高风险门禁：写操作要求 admin 绑定手机号
    async def _seed_admin_phone_bound() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin_id,
                    username="it_admin_export",
                    password_hash=hash_password(password="Abcdef!2345"),
                    status="ACTIVE",
                    phone="13800138000",
                )
            )
            await session.commit()

    asyncio.run(_seed_admin_phone_bound())

    # 用现有 admin 创建 dealer 账号，拿到 dealerId
    r = client.post(
        "/api/v1/admin/dealer-users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "it_dealer_user_export_1", "dealerName": "IT Dealer Export 1"},
    )
    assert r.status_code == 200
    dealer_id = r.json()["data"]["dealerUser"]["dealerId"]

    # seed 一条订单（服务包订单），created_at 落在 dateFrom/dateTo（北京时间自然日）内
    order_id = str(uuid4())
    # 固定 UTC 时间，避免“当天”在不同时区/不同执行时间下导致 dateFrom/dateTo 漂移
    # UTC 2026-01-06 23:00:00 == 北京 2026-01-07 07:00:00
    now = datetime(2026, 1, 6, 23, 0, 0, tzinfo=UTC).replace(tzinfo=None)
    beijing_day = "2026-01-07"

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Order(
                    id=order_id,
                    user_id=str(uuid4()),
                    order_type="SERVICE_PACKAGE",
                    total_amount=88.0,
                    payment_method="WECHAT",
                    payment_status="PAID",
                    dealer_id=dealer_id,
                    dealer_link_id=str(uuid4()),
                    fulfillment_type=None,
                    fulfillment_status=None,
                    goods_amount=0.0,
                    shipping_amount=0.0,
                    shipping_address_json=None,
                    reservation_expires_at=None,
                    shipping_carrier=None,
                    shipping_tracking_no=None,
                    shipped_at=None,
                    delivered_at=None,
                    received_at=None,
                    created_at=now,
                    paid_at=now,
                    confirmed_at=None,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    # 1) 缺 dateFrom/dateTo -> 400
    r0 = client.get(
        "/api/v1/dealer/orders/export",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"dealerId": dealer_id},
    )
    assert r0.status_code == 400
    assert r0.json()["success"] is False
    assert r0.json()["error"]["code"] == "INVALID_ARGUMENT"

    # 2) 正常导出：200，Content-Disposition attachment，CSV 含 BOM + 订单号
    r1 = client.get(
        "/api/v1/dealer/orders/export",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"dealerId": dealer_id, "dateFrom": beijing_day, "dateTo": beijing_day},
    )
    assert r1.status_code == 200
    assert "attachment" in (r1.headers.get("Content-Disposition") or "")
    body = r1.content.decode("utf-8")
    assert body.startswith("\ufeff")
    assert order_id in body

    # 3) 审计：EXPORT_DEALER_ORDERS + resourceId=dealerId 至少 1 条
    r_audit = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"resourceType": "EXPORT_DEALER_ORDERS", "resourceId": dealer_id, "page": 1, "pageSize": 50},
    )
    assert r_audit.status_code == 200
    assert r_audit.json()["data"]["total"] >= 1


def test_export_over_max_rows_rejected_400():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    async def _seed_admin_phone_bound() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin_id,
                    username="it_admin_export_2",
                    password_hash=hash_password(password="Abcdef!2345"),
                    status="ACTIVE",
                    phone="13800138000",
                )
            )
            await session.commit()

    asyncio.run(_seed_admin_phone_bound())

    r = client.post(
        "/api/v1/admin/dealer-users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "it_dealer_user_export_2", "dealerName": "IT Dealer Export 2"},
    )
    assert r.status_code == 200
    dealer_id = r.json()["data"]["dealerUser"]["dealerId"]

    day = datetime(2025, 12, 1, tzinfo=UTC).replace(tzinfo=None)

    async def _seed_many() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add_all(
                [
                    Order(
                        id=str(uuid4()),
                        user_id=str(uuid4()),
                        order_type="SERVICE_PACKAGE",
                        total_amount=1.0,
                        payment_method="WECHAT",
                        payment_status="PAID",
                        dealer_id=dealer_id,
                        dealer_link_id=None,
                        fulfillment_type=None,
                        fulfillment_status=None,
                        goods_amount=0.0,
                        shipping_amount=0.0,
                        shipping_address_json=None,
                        reservation_expires_at=None,
                        shipping_carrier=None,
                        shipping_tracking_no=None,
                        shipped_at=None,
                        delivered_at=None,
                        received_at=None,
                        created_at=day,
                        paid_at=day,
                        confirmed_at=None,
                    )
                    for _ in range(5001)
                ]
            )
            await session.commit()

    asyncio.run(_seed_many())

    r1 = client.get(
        "/api/v1/dealer/orders/export",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"dealerId": dealer_id, "dateFrom": "2025-12-01", "dateTo": "2025-12-01"},
    )
    assert r1.status_code == 400
    assert r1.json()["success"] is False
    assert r1.json()["error"]["code"] == "INVALID_ARGUMENT"


def test_export_date_filter_is_beijing_day_boundary():
    """证明：导出 dateFrom/dateTo 按北京时间自然日边界解释，而不是 UTC 00:00~23:59:59。"""

    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    async def _seed_admin_phone_bound() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin_id,
                    username="it_admin_export_3",
                    password_hash=hash_password(password="Abcdef!2345"),
                    status="ACTIVE",
                    phone="13800138000",
                )
            )
            await session.commit()

    asyncio.run(_seed_admin_phone_bound())

    r = client.post(
        "/api/v1/admin/dealer-users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "it_dealer_user_export_3", "dealerName": "IT Dealer Export 3"},
    )
    assert r.status_code == 200
    dealer_id = r.json()["data"]["dealerUser"]["dealerId"]

    # 北京时间 2026-01-07 00:00:00 == UTC 2026-01-06 16:00:00
    order_before = str(uuid4())
    order_at = str(uuid4())
    order_inside = str(uuid4())

    async def _seed_three() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add_all(
                [
                    Order(
                        id=order_before,
                        user_id=str(uuid4()),
                        order_type="SERVICE_PACKAGE",
                        total_amount=1.0,
                        payment_method="WECHAT",
                        payment_status="PAID",
                        dealer_id=dealer_id,
                        dealer_link_id=None,
                        fulfillment_type=None,
                        fulfillment_status=None,
                        goods_amount=0.0,
                        shipping_amount=0.0,
                        shipping_address_json=None,
                        reservation_expires_at=None,
                        shipping_carrier=None,
                        shipping_tracking_no=None,
                        shipped_at=None,
                        delivered_at=None,
                        received_at=None,
                        created_at=datetime(2026, 1, 6, 15, 59, 59, tzinfo=UTC).replace(tzinfo=None),
                        paid_at=datetime(2026, 1, 6, 15, 59, 59, tzinfo=UTC).replace(tzinfo=None),
                        confirmed_at=None,
                    ),
                    Order(
                        id=order_at,
                        user_id=str(uuid4()),
                        order_type="SERVICE_PACKAGE",
                        total_amount=1.0,
                        payment_method="WECHAT",
                        payment_status="PAID",
                        dealer_id=dealer_id,
                        dealer_link_id=None,
                        fulfillment_type=None,
                        fulfillment_status=None,
                        goods_amount=0.0,
                        shipping_amount=0.0,
                        shipping_address_json=None,
                        reservation_expires_at=None,
                        shipping_carrier=None,
                        shipping_tracking_no=None,
                        shipped_at=None,
                        delivered_at=None,
                        received_at=None,
                        created_at=datetime(2026, 1, 6, 16, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                        paid_at=datetime(2026, 1, 6, 16, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                        confirmed_at=None,
                    ),
                    Order(
                        id=order_inside,
                        user_id=str(uuid4()),
                        order_type="SERVICE_PACKAGE",
                        total_amount=1.0,
                        payment_method="WECHAT",
                        payment_status="PAID",
                        dealer_id=dealer_id,
                        dealer_link_id=None,
                        fulfillment_type=None,
                        fulfillment_status=None,
                        goods_amount=0.0,
                        shipping_amount=0.0,
                        shipping_address_json=None,
                        reservation_expires_at=None,
                        shipping_carrier=None,
                        shipping_tracking_no=None,
                        shipped_at=None,
                        delivered_at=None,
                        received_at=None,
                        created_at=datetime(2026, 1, 6, 23, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                        paid_at=datetime(2026, 1, 6, 23, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                        confirmed_at=None,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(_seed_three())

    r_csv = client.get(
        "/api/v1/dealer/orders/export",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"dealerId": dealer_id, "dateFrom": "2026-01-07", "dateTo": "2026-01-07"},
    )
    assert r_csv.status_code == 200
    body = r_csv.content.decode("utf-8")
    assert order_before not in body
    assert order_at in body
    assert order_inside in body


