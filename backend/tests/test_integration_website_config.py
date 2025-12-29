"""集成测试：Website 只读配置下发（SystemConfig）。

规格来源：
- specs/health-services-platform/design.md -> I. Website 只读配置下发（v1 最小契约）
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
from app.models.enums import CommonEnabledStatus, VenuePublishStatus
from app.models.system_config import SystemConfig
from app.models.venue import Venue
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


def test_website_recommended_venues_and_footer():
    asyncio.run(_reset_db_and_redis())

    v1 = str(uuid4())
    v2 = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add_all(
                [
                    Venue(
                        id=v1,
                        provider_id=str(uuid4()),
                        name="场所A",
                        logo_url=None,
                        cover_image_url=None,
                        image_urls=None,
                        description=None,
                        country_code="COUNTRY:CN",
                        province_code="PROVINCE:110000",
                        city_code="CITY:110100",
                        address="addr",
                        lat=None,
                        lng=None,
                        contact_phone="13800000000",
                        business_hours=None,
                        tags=["t1"],
                        publish_status=VenuePublishStatus.PUBLISHED.value,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    ),
                    Venue(
                        id=v2,
                        provider_id=str(uuid4()),
                        name="场所B",
                        logo_url=None,
                        cover_image_url=None,
                        image_urls=None,
                        description=None,
                        country_code="COUNTRY:CN",
                        province_code="PROVINCE:310000",
                        city_code="CITY:310100",
                        address="addr2",
                        lat=None,
                        lng=None,
                        contact_phone=None,
                        business_hours=None,
                        tags=[],
                        publish_status=VenuePublishStatus.PUBLISHED.value,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    ),
                    SystemConfig(
                        id=str(uuid4()),
                        key="WEBSITE_HOME_RECOMMENDED_VENUES",
                        status=CommonEnabledStatus.ENABLED.value,
                        value_json={"version": "v1", "items": [{"venueId": v2}, {"venueId": v1}]},
                        description="test",
                    ),
                    SystemConfig(
                        id=str(uuid4()),
                        key="WEBSITE_FOOTER_CONFIG",
                        status=CommonEnabledStatus.ENABLED.value,
                        value_json={"version": "v2", "companyName": "c", "icpBeianNo": "x"},
                        description="test",
                    ),
                ]
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)

    r1 = client.get("/api/v1/website/home/recommended-venues")
    assert r1.status_code == 200
    data = r1.json()["data"]
    assert data["version"] == "v1"
    # 返回顺序与配置一致
    assert [x["id"] for x in data["items"]] == [v2, v1]
    assert data["items"][1]["contactPhoneMasked"] == "138****0000"

    r2 = client.get("/api/v1/website/footer/config")
    assert r2.status_code == 200
    assert r2.json()["data"]["companyName"] == "c"

