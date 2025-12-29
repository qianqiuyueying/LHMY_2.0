"""集成测试：城市配置读侧（REGION_CITIES）。

规格来源：
- specs/health-services-platform/design.md -> F-1. 城市配置读侧（跨端复用，v1 固化）
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


def test_regions_cities_filters_and_default():
    asyncio.run(_reset_db_and_redis())

    cfg_id = str(uuid4())
    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                SystemConfig(
                    id=cfg_id,
                    key="REGION_CITIES",
                    status=CommonEnabledStatus.ENABLED.value,
                    value_json={
                        "version": "1",
                        "defaultCode": "CITY:110100",
                        "items": [
                            {"code": "CITY:110100", "name": "北京", "sort": 2, "enabled": True, "published": True},
                            {"code": "CITY:310100", "name": "上海", "sort": 1, "enabled": True, "published": True},
                            {"code": "CITY:999999", "name": "隐藏", "sort": 0, "enabled": False, "published": True},
                            {"code": "CITY:888888", "name": "未发布", "sort": 0, "enabled": True, "published": False},
                        ],
                    },
                    description="test",
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    r = client.get("/api/v1/regions/cities")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["version"] == "1"
    # 过滤掉 disabled / unpublished
    assert [x["code"] for x in data["items"]] == ["CITY:310100", "CITY:110100"]
    # defaultCode 必须在 items 中
    assert data["defaultCode"] == "CITY:110100"

