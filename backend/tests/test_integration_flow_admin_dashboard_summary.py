"""集成测试：FLOW-ADMIN-DASHBOARD（仪表盘 summary 契约 + 错误码）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9L（字段名/结构、refundRequestCount 口径、非法 range=400 INVALID_ARGUMENT）
- specs-prod/admin/tasks.md#FLOW-ADMIN-DASHBOARD
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


def test_admin_dashboard_summary_contract_and_guards_and_invalid_range_400():
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    # 未登录 -> 401
    r0 = client.get("/api/v1/admin/dashboard/summary")
    assert r0.status_code == 401
    assert r0.json()["error"]["code"] == "UNAUTHENTICATED"

    # 非 ADMIN -> 403
    user_token = create_user_token(user_id="00000000-0000-0000-0000-00000000u001")
    r_forbidden = client.get(
        "/api/v1/admin/dashboard/summary",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r_forbidden.status_code == 403
    assert r_forbidden.json()["error"]["code"] == "FORBIDDEN"

    # ADMIN 正常 -> 200 且结构对齐契约（空库也应返回完整结构）
    admin_token, _ = create_admin_token(admin_id="00000000-0000-0000-0000-00000000a001")
    r_ok = client.get(
        "/api/v1/admin/dashboard/summary?range=7d",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert body["success"] is True
    assert body["error"] is None
    assert isinstance(body.get("requestId"), str) and body["requestId"]
    data = body["data"]
    assert data["range"] == "7d"
    assert set(data.keys()) == {"range", "today", "trends", "todos"}
    assert set(data["today"].keys()) == {
        "newMemberCount",
        "servicePackagePaidCount",
        "ecommercePaidCount",
        "refundRequestCount",
        "redemptionSuccessCount",
    }
    assert set(data["trends"].keys()) == {"servicePackageOrders", "ecommerceOrders", "redemptions"}
    assert set(data["todos"].keys()) == {"refundUnderReviewCount", "abnormalOrderCount", "enterpriseBindingPendingCount"}
    assert len(data["trends"]["servicePackageOrders"]) == 7
    assert len(data["trends"]["ecommerceOrders"]) == 7
    assert len(data["trends"]["redemptions"]) == 7

    # 非法 range -> 400 INVALID_ARGUMENT（不走 422）
    r_bad = client.get(
        "/api/v1/admin/dashboard/summary?range=bad",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_bad.status_code == 400
    assert r_bad.json()["error"]["code"] == "INVALID_ARGUMENT"


