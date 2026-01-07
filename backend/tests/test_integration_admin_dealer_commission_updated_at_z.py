"""集成测试：结算域（分账规则）updatedAt 必须为 UTC+Z 字符串。

动机：该字段存储在 SystemConfig.value_json（字符串），容易因为 isoformat() 写入 '+00:00' 而非 'Z'。
规格来源：specs/health-services-platform/time-and-timezone.md（timestamp 出参统一 UTC+Z）。
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


async def _reset_db_and_redis() -> None:
    r = get_redis()
    await r.flushdb()

    session_factory = get_session_factory()
    async with session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


def test_admin_dealer_commission_updated_at_is_utc_z():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    r = client.put(
        "/api/v1/admin/dealer-commission",
        headers={"Authorization": f"Bearer {token}"},
        json={"defaultRate": 0.12, "dealerOverrides": {}},
    )
    assert r.status_code == 200
    assert str(r.json()["data"]["updatedAt"]).endswith("Z")

    r2 = client.get("/api/v1/admin/dealer-commission", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert str(r2.json()["data"]["updatedAt"]).endswith("Z")


