"""
Seed demo published venues for website (for minimal data / showcase).

用途：
- 满足 `specs/功能实现/website/minimal-data.md` 中“首页推荐场所至少 3 条”的门槛（用于官网展示与回归）。

运行方式（docker compose 环境）：
  docker compose exec backend sh -lc "PYTHONPATH=/app /app/.venv/bin/python /app/scripts/seed_website_demo_venues.py"
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import select

from app.models.enums import VenuePublishStatus
from app.models.provider import Provider
from app.models.venue import Venue
from app.utils.db import get_engine, get_session_factory


DEMO_PROVIDER_ID = "00000000-0000-0000-0000-000000000101"

VENUES = [
    {
        "id": "00000000-0000-0000-0000-000000000102",
        "name": "DEMO 场所（Venue）",
        "address": "DEMO 地址",
        "contact_phone": "010-12345678",
        "business_hours": "09:00-18:00",
        "tags": ["体检", "预约"],
    },
    {
        "id": "00000000-0000-0000-0000-000000000202",
        "name": "DEMO 场所二（Venue）",
        "address": "DEMO 地址（二）",
        "contact_phone": "021-12345678",
        "business_hours": "10:00-19:00",
        "tags": ["健康管理", "企业服务"],
    },
    {
        "id": "00000000-0000-0000-0000-000000000302",
        "name": "DEMO 场所三（Venue）",
        "address": "DEMO 地址（三）",
        "contact_phone": "0755-12345678",
        "business_hours": "08:30-17:30",
        "tags": ["康复", "理疗"],
    },
]


async def _main() -> None:
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    session_factory = get_session_factory()
    async with session_factory() as session:
        provider = (await session.scalars(select(Provider).where(Provider.id == DEMO_PROVIDER_ID).limit(1))).first()
        if provider is None:
            provider = Provider(id=DEMO_PROVIDER_ID, name="DEMO 场所方（Provider）")
            session.add(provider)

        for v in VENUES:
            existing = (await session.scalars(select(Venue).where(Venue.id == v["id"]).limit(1))).first()
            if existing is None:
                existing = Venue(
                    id=v["id"],
                    provider_id=DEMO_PROVIDER_ID,
                    name=v["name"],
                    publish_status=VenuePublishStatus.PUBLISHED.value,
                    address=v["address"],
                    contact_phone=v["contact_phone"],
                    business_hours=v["business_hours"],
                    tags=v["tags"],
                    created_at=now,
                    updated_at=now,
                )
                session.add(existing)
            else:
                existing.name = v["name"]
                existing.publish_status = VenuePublishStatus.PUBLISHED.value
                existing.address = v["address"]
                existing.contact_phone = v["contact_phone"]
                existing.business_hours = v["business_hours"]
                existing.tags = v["tags"]
                existing.updated_at = now

        await session.commit()

    print(f"OK: seeded {len(VENUES)} demo venues (PUBLISHED)")
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(_main())


