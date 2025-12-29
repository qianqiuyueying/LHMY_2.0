"""
Seed / upsert WEBSITE_HOME_RECOMMENDED_VENUES into SystemConfig.

用途：
- 让官网首页“推荐场所/服务”区块在部署环境具备最小可展示数据（避免空态）。

运行方式（docker compose 环境）：
- 自动选取最近的已发布场所（默认 3 条）：
  docker compose exec backend sh -lc "PYTHONPATH=/app /app/.venv/bin/python /app/scripts/seed_website_home_recommended_venues.py"
- 指定数量：
  docker compose exec backend sh -lc "PYTHONPATH=/app /app/.venv/bin/python /app/scripts/seed_website_home_recommended_venues.py --limit 6"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from uuid import uuid4

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import select

from app.models.enums import CommonEnabledStatus, VenuePublishStatus
from app.models.system_config import SystemConfig
from app.models.venue import Venue
from app.utils.db import get_engine, get_session_factory


KEY = "WEBSITE_HOME_RECOMMENDED_VENUES"


def _now_version() -> str:
    return str(int(time.time()))


async def _main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=3)
    args = p.parse_args()

    limit = max(1, min(12, int(args.limit or 3)))

    session_factory = get_session_factory()
    async with session_factory() as session:
        venues = (
            await session.scalars(
                select(Venue)
                .where(Venue.publish_status == VenuePublishStatus.PUBLISHED.value)
                .order_by(Venue.updated_at.desc(), Venue.created_at.desc())
                .limit(limit)
            )
        ).all()

        items = [{"venueId": v.id} for v in venues]
        value_json = {"version": _now_version(), "items": items, "title": "推荐场所/服务"}

        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == KEY).limit(1))).first()
        if cfg is None:
            cfg = SystemConfig(
                id=str(uuid4()),
                key=KEY,
                value_json=value_json,
                description="Seeded by scripts/seed_website_home_recommended_venues.py",
                status=CommonEnabledStatus.ENABLED.value,
            )
            session.add(cfg)
        else:
            cfg.value_json = value_json
            cfg.status = CommonEnabledStatus.ENABLED.value
            cfg.description = "Updated by scripts/seed_website_home_recommended_venues.py"

        await session.commit()

    print(f"OK: upserted {KEY} version={value_json.get('version')} items={len(items)}")
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(_main())


