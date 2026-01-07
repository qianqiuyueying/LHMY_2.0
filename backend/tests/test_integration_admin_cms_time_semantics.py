"""集成测试：CMS 时间口径（Admin）——过滤北京自然日 + effectiveFrom/effectiveUntil 支持 Z。

规格来源（单一真相来源）：
- specs/health-services-platform/time-and-timezone.md#3
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.cms_content import CmsContent
from app.models.enums import CmsContentStatus
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


def test_admin_cms_contents_date_filter_beijing_day_and_effective_parse_z_roundtrip():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    token, _ = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # 北京时间 2026-01-07 00:00:00 == UTC 2026-01-06 16:00:00
    before_id = str(uuid4())
    at_id = str(uuid4())
    inside_id = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add_all(
                [
                    CmsContent(
                        id=before_id,
                        channel_id=None,
                        title="before",
                        cover_image_url=None,
                        summary=None,
                        content_md=None,
                        content_html="<p>x</p>",
                        status=CmsContentStatus.DRAFT.value,
                        published_at=None,
                        mp_status=CmsContentStatus.DRAFT.value,
                        mp_published_at=None,
                        effective_from=None,
                        effective_until=None,
                        created_at=datetime(2026, 1, 6, 15, 59, 59, tzinfo=UTC).replace(tzinfo=None),
                        updated_at=datetime(2026, 1, 6, 15, 59, 59, tzinfo=UTC).replace(tzinfo=None),
                    ),
                    CmsContent(
                        id=at_id,
                        channel_id=None,
                        title="at",
                        cover_image_url=None,
                        summary=None,
                        content_md=None,
                        content_html="<p>x</p>",
                        status=CmsContentStatus.DRAFT.value,
                        published_at=None,
                        mp_status=CmsContentStatus.DRAFT.value,
                        mp_published_at=None,
                        effective_from=None,
                        effective_until=None,
                        created_at=datetime(2026, 1, 6, 16, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                        updated_at=datetime(2026, 1, 6, 16, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                    ),
                    CmsContent(
                        id=inside_id,
                        channel_id=None,
                        title="inside",
                        cover_image_url=None,
                        summary=None,
                        content_md=None,
                        content_html="<p>x</p>",
                        status=CmsContentStatus.DRAFT.value,
                        published_at=None,
                        mp_status=CmsContentStatus.DRAFT.value,
                        mp_published_at=None,
                        effective_from=None,
                        effective_until=None,
                        created_at=datetime(2026, 1, 6, 23, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                        updated_at=datetime(2026, 1, 6, 23, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                    ),
                ]
            )
            await session.commit()

    asyncio.run(_seed())

    r = client.get(
        "/api/v1/admin/cms/contents",
        headers={"Authorization": f"Bearer {token}"},
        params={"dateFrom": "2026-01-07", "dateTo": "2026-01-07", "page": 1, "pageSize": 50, "includeContent": False},
    )
    assert r.status_code == 200
    ids = {x["id"] for x in (r.json()["data"]["items"] or [])}
    assert before_id not in ids
    assert at_id in ids
    assert inside_id in ids

    # effectiveFrom/effectiveUntil roundtrip: 支持 Z 输入
    r2 = client.post(
        "/api/v1/admin/cms/contents",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "eff",
            "summary": "s",
            "contentHtml": "<p>ok</p>",
            "effectiveFrom": "2026-01-07T00:00:00Z",
            "effectiveUntil": "2026-01-08T00:00:00Z",
        },
    )
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert str(data["effectiveFrom"]).endswith("Z")
    assert str(data["effectiveUntil"]).endswith("Z")


