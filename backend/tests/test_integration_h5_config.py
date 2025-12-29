"""集成测试：H5 只读配置下发（SystemConfig）。

规格来源：
- specs/health-services-platform/design.md -> H. H5 只读配置下发（v1 最小契约）
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.enums import CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.utils.db import get_session_factory
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


def test_h5_config_endpoints():
    asyncio.run(_reset_db_and_redis())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add_all(
                [
                    SystemConfig(
                        id=str(uuid4()),
                        key="H5_LANDING_FAQ_TERMS",
                        status=CommonEnabledStatus.ENABLED.value,
                        value_json={"version": "v1", "items": [{"q": "q1", "a": "a1"}], "termsText": "t"},
                        description="test",
                    ),
                    SystemConfig(
                        id=str(uuid4()),
                        key="H5_SERVICE_AGREEMENT",
                        status=CommonEnabledStatus.ENABLED.value,
                        value_json={"version": "v2", "title": "协议", "contentHtml": "<p>ok</p>"},
                        description="test",
                    ),
                    SystemConfig(
                        id=str(uuid4()),
                        key="H5_MINI_PROGRAM_LAUNCH",
                        status=CommonEnabledStatus.ENABLED.value,
                        value_json={"version": "v3", "appid": "wx123", "path": "/pages/entitlements", "fallbackText": "fb"},
                        description="test",
                    ),
                ]
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)

    r1 = client.get("/api/v1/h5/landing/faq-terms")
    assert r1.status_code == 200
    assert r1.json()["data"]["version"] == "v1"
    assert r1.json()["data"]["termsText"] == "t"
    assert r1.json()["data"]["items"][0]["q"] == "q1"

    r2 = client.get("/api/v1/h5/legal/service-agreement")
    assert r2.status_code == 200
    assert r2.json()["data"]["version"] == "v2"
    assert r2.json()["data"]["title"] == "协议"

    r3 = client.get("/api/v1/h5/mini-program/launch")
    assert r3.status_code == 200
    assert r3.json()["data"]["version"] == "v3"
    assert r3.json()["data"]["appid"] == "wx123"

