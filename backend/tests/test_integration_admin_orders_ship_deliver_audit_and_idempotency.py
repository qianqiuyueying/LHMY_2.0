"""集成测试：Admin 订单监管（发货/妥投）审计 + 幂等口径证明（Batch2）。

规格来源（单一真相来源）：
- specs-prod/admin/api-contracts.md#9B 订单监管（Admin Orders）
- specs-prod/admin/api-contracts.md#1.4 状态机写操作的统一口径
- specs-prod/admin/tasks.md#FLOW-ORDERS
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
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.enums import OrderFulfillmentStatus, PaymentMethod, PaymentStatus, ProductFulfillmentType, ProductStatus
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
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


async def _seed_paid_physical_goods_order(*, fulfillment_status: str | None) -> str:
    order_id = str(uuid4())
    user_id = str(uuid4())
    product_id = str(uuid4())

    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Product(
                id=product_id,
                provider_id=str(uuid4()),
                title="IT Product",
                description_md="d",
                description_html="d",
                cover_image_url=None,
                images_json=None,
                price=10.0,
                list_price=10.0,
                status=ProductStatus.ON_SALE.value,
                fulfillment_type=ProductFulfillmentType.PHYSICAL_GOODS.value,
                created_at=datetime.now(tz=UTC).replace(tzinfo=None),
                updated_at=datetime.now(tz=UTC).replace(tzinfo=None),
            )
        )

        session.add(
            Order(
                id=order_id,
                user_id=user_id,
                order_type="PRODUCT",
                total_amount=10.0,
                payment_method=PaymentMethod.WECHAT.value,
                payment_status=PaymentStatus.PAID.value,
                dealer_id=None,
                dealer_link_id=None,
                fulfillment_type=ProductFulfillmentType.PHYSICAL_GOODS.value,
                fulfillment_status=fulfillment_status,
                goods_amount=10.0,
                shipping_amount=0.0,
                shipping_address_json={"name": "it", "phoneMasked": "138****0000"},
                reservation_expires_at=None,
                shipping_carrier=None,
                shipping_tracking_no=None,
                shipped_at=None,
                delivered_at=None,
                received_at=None,
                created_at=datetime.now(tz=UTC).replace(tzinfo=None),
                paid_at=datetime.now(tz=UTC).replace(tzinfo=None),
                confirmed_at=None,
            )
        )

        session.add(
            OrderItem(
                id=str(uuid4()),
                order_id=order_id,
                item_type="PRODUCT",
                item_id=product_id,
                title="IT Product",
                quantity=1,
                unit_price=10.0,
                total_price=10.0,
                service_package_template_id=None,
                region_scope=None,
                tier=None,
                created_at=datetime.now(tz=UTC).replace(tzinfo=None),
            )
        )
        await session.commit()

    return order_id


def test_admin_ship_idempotent_noop_and_audited():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    order_id = asyncio.run(_seed_paid_physical_goods_order(fulfillment_status=OrderFulfillmentStatus.NOT_SHIPPED.value))

    # 1) 首次发货：200 + SHIPPED
    r1 = client.post(
        f"/api/v1/admin/orders/{order_id}/ship",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"carrier": "SF", "trackingNo": "SF00001234"},
    )
    assert r1.status_code == 200
    assert r1.json()["success"] is True
    assert r1.json()["data"]["fulfillmentStatus"] == OrderFulfillmentStatus.SHIPPED.value

    # 2) 重复提交：相同运单信息 -> 200 no-op
    r2 = client.post(
        f"/api/v1/admin/orders/{order_id}/ship",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"carrier": "SF", "trackingNo": "SF00001234"},
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert r2.json()["data"]["fulfillmentStatus"] == OrderFulfillmentStatus.SHIPPED.value

    # 3) 重复提交：不同运单信息 -> 409 INVALID_STATE_TRANSITION
    r3 = client.post(
        f"/api/v1/admin/orders/{order_id}/ship",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"carrier": "YTO", "trackingNo": "YTO9999"},
    )
    assert r3.status_code == 409
    assert r3.json()["success"] is False
    assert r3.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # 4) 审计：至少 1 条 ORDER 资源审计
    r_audit = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"resourceType": "ORDER", "resourceId": order_id, "page": 1, "pageSize": 50},
    )
    assert r_audit.status_code == 200
    assert r_audit.json()["data"]["total"] >= 1
    assert any((x.get("metadata") or {}).get("afterFulfillmentStatus") == OrderFulfillmentStatus.SHIPPED.value for x in r_audit.json()["data"]["items"])


def test_admin_deliver_idempotent_noop_and_audited():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    order_id = asyncio.run(_seed_paid_physical_goods_order(fulfillment_status=OrderFulfillmentStatus.SHIPPED.value))

    # 1) 首次妥投：200 + DELIVERED
    r1 = client.post(
        f"/api/v1/admin/orders/{order_id}/deliver",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["success"] is True
    assert r1.json()["data"]["fulfillmentStatus"] == OrderFulfillmentStatus.DELIVERED.value

    # 2) 重复提交：已 DELIVERED -> 200 no-op
    r2 = client.post(
        f"/api/v1/admin/orders/{order_id}/deliver",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert r2.json()["data"]["fulfillmentStatus"] == OrderFulfillmentStatus.DELIVERED.value

    # 3) 审计：至少 1 条 ORDER 资源审计（afterFulfillmentStatus=DELIVERED）
    r_audit = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"resourceType": "ORDER", "resourceId": order_id, "page": 1, "pageSize": 50},
    )
    assert r_audit.status_code == 200
    assert any((x.get("metadata") or {}).get("afterFulfillmentStatus") == OrderFulfillmentStatus.DELIVERED.value for x in r_audit.json()["data"]["items"])


def test_admin_ship_deliver_business_audit_count_not_explosive():
    """证明：业务审计落点是稳定的（至少各 1 条），且 no-op 不额外刷业务审计。"""

    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    order_id = asyncio.run(_seed_paid_physical_goods_order(fulfillment_status=OrderFulfillmentStatus.NOT_SHIPPED.value))

    client.post(
        f"/api/v1/admin/orders/{order_id}/ship",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"carrier": "SF", "trackingNo": "SF00001234"},
    )
    client.post(
        f"/api/v1/admin/orders/{order_id}/ship",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"carrier": "SF", "trackingNo": "SF00001234"},
    )
    client.post(
        f"/api/v1/admin/orders/{order_id}/deliver",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/v1/admin/orders/{order_id}/deliver",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    async def _count_order_audit() -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(func.count()).select_from(AuditLog).where(AuditLog.resource_type == "ORDER", AuditLog.resource_id == order_id)
            return int((await session.execute(stmt)).scalar() or 0)

    # ship 1 条 + deliver 1 条（业务审计）；no-op 不追加
    assert asyncio.run(_count_order_audit()) == 2


