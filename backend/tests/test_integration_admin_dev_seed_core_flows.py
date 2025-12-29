"""集成测试：演示数据初始化 + 核心闭环（admin-dev）。

规格来源：
- specs/功能实现/admin/tasks.md
  - B01/B02/B03/B04/B05（让页面不再只有空态 + 可操作闭环）
  - F01（/api/v1/openapi.json 可访问）

说明：
- 该文件为“跑通最短闭环”的集成测试：用 admin/dev/seed 生成固定演示数据，然后用接口执行关键动作并断言结果。
"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
from app.utils.redis_client import get_redis

pytestmark = pytest.mark.skipif(os.getenv("RUN_INTEGRATION_TESTS") != "1", reason="integration tests disabled")

def _assert_page_shape(data: dict) -> None:
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pageSize" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    assert isinstance(data["page"], int)
    assert isinstance(data["pageSize"], int)


async def _reset_db_and_redis() -> None:
    r = get_redis()
    await r.flushdb()

    session_factory = get_session_factory()
    async with session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


def test_admin_dev_seed_and_core_actions_happy_path():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # 1) OpenAPI 兼容入口
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200

    # 2) Seed
    r = client.post("/api/v1/admin/dev/seed", headers={"Authorization": f"Bearer {token}"}, json={"reset": True})
    assert r.status_code == 200
    payload = r.json()
    assert payload["success"] is True
    ids = payload["data"]["ids"]
    assert ids["productId"]
    assert ids["productId2"]
    assert ids["afterSaleId"]
    assert ids["afterSaleId2"]
    assert ids["entitlementId2"]
    assert ids["voucherCode2"]
    assert ids["bookingId"]
    assert ids["bookingId2"]

    product_id = ids["productId"]
    product_id2 = ids["productId2"]
    after_sale_id = ids["afterSaleId"]
    after_sale_id2 = ids["afterSaleId2"]
    entitlement_id2 = ids["entitlementId2"]
    voucher_code2 = ids["voucherCode2"]
    booking_id = ids["bookingId"]
    booking_id2 = ids["bookingId2"]

    # 3) 商品：approve/reject/off-shelf
    r = client.get(
        "/api/v1/admin/products",
        headers={"Authorization": f"Bearer {token}"},
        params={"status": "PENDING_REVIEW", "page": 1, "pageSize": 20},
    )
    assert r.status_code == 200
    _assert_page_shape(r.json()["data"])
    assert r.json()["data"]["total"] >= 1

    r = client.put(f"/api/v1/admin/products/{product_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ON_SALE"

    r = client.put(f"/api/v1/admin/products/{product_id}/off-shelf", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "OFF_SHELF"

    r = client.put(f"/api/v1/admin/products/{product_id2}/reject", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "REJECTED"

    # 4) 售后：同意/驳回
    r = client.get(
        "/api/v1/admin/after-sales",
        headers={"Authorization": f"Bearer {token}"},
        params={"status": "UNDER_REVIEW", "page": 1, "pageSize": 20},
    )
    assert r.status_code == 200
    _assert_page_shape(r.json()["data"])
    assert r.json()["data"]["total"] >= 1

    r = client.put(
        f"/api/v1/admin/after-sales/{after_sale_id}/decide",
        headers={"Authorization": f"Bearer {token}"},
        json={"decision": "APPROVE", "decisionNotes": "demo approve"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["decision"] == "APPROVE"
    assert r.json()["data"]["status"] == "CLOSED"

    r = client.put(
        f"/api/v1/admin/after-sales/{after_sale_id2}/decide",
        headers={"Authorization": f"Bearer {token}"},
        json={"decision": "REJECT", "decisionNotes": "demo reject"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["decision"] == "REJECT"
    assert r.json()["data"]["status"] == "CLOSED"

    # 5) 权益核销 + 核销记录
    r = client.post(
        f"/api/v1/entitlements/{entitlement_id2}/redeem",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "it:redeem:1"},
        json={"venueId": ids["venueId"], "redemptionMethod": "VOUCHER_CODE", "voucherCode": voucher_code2},
    )
    assert r.status_code == 200
    res = r.json()["data"]
    assert res["status"] == "SUCCESS"
    redemption_record_id = res["redemptionRecordId"]

    r = client.get(
        "/api/v1/admin/redemptions",
        headers={"Authorization": f"Bearer {token}"},
        params={"page": 1, "pageSize": 20},
    )
    assert r.status_code == 200
    _assert_page_shape(r.json()["data"])
    ids_in_list = {x["id"] for x in r.json()["data"]["items"]}
    assert redemption_record_id in ids_in_list

    # 6) 预约：确认/取消（含取消原因）
    r = client.get(
        "/api/v1/provider/bookings",
        headers={"Authorization": f"Bearer {token}"},
        params={"status": "PENDING", "page": 1, "pageSize": 20},
    )
    assert r.status_code == 200
    _assert_page_shape(r.json()["data"])

    r = client.put(
        f"/api/v1/bookings/{booking_id}/confirm",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "it:confirm:1"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "CONFIRMED"

    r = client.delete(
        f"/api/v1/admin/bookings/{booking_id2}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "it:cancel:1"},
        json={"reason": "demo cancel"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "CANCELLED"

