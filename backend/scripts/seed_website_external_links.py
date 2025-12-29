"""
Seed / upsert WEBSITE_EXTERNAL_LINKS into SystemConfig.

用途：
- 官网导流外链由后端运行时下发（可运营修改），避免前端构建时写死。
- 当前 h5/小程序未上线时，允许使用“可识别的假外链”（包含 LHMY 字样）。

运行方式（docker compose 环境）：
- demo（写入 LHMY 假外链）：docker compose exec backend sh -lc "PYTHONPATH=/app /app/.venv/bin/python /app/scripts/seed_website_external_links.py --demo"
- 显式传参：
  docker compose exec backend sh -lc "PYTHONPATH=/app /app/.venv/bin/python /app/scripts/seed_website_external_links.py --mini https://LHMY.example.com/mini --h5 https://LHMY.example.com/h5-buy"
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

from app.models.enums import CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.utils.db import get_engine, get_session_factory


KEY = "WEBSITE_EXTERNAL_LINKS"


def _now_version() -> str:
    return str(int(time.time()))


def _ensure_http_url(url: str) -> str:
    u = str(url or "").strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        raise SystemExit("URL 必须以 http:// 或 https:// 开头")
    return u


async def _main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    p.add_argument("--mini", dest="mini_url")
    p.add_argument("--h5", dest="h5_url")
    args = p.parse_args()

    if args.demo:
        mini = "https://LHMY.example.com/mini-program"
        h5 = "https://LHMY.example.com/h5-buy"
    else:
        if not args.mini_url or not args.h5_url:
            raise SystemExit("缺少 --mini 与 --h5（或使用 --demo）")
        mini = _ensure_http_url(args.mini_url)
        h5 = _ensure_http_url(args.h5_url)

    value_json = {"version": _now_version(), "miniProgramUrl": mini, "h5BuyUrl": h5}

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == KEY).limit(1))).first()
        if cfg is None:
            cfg = SystemConfig(
                id=str(uuid4()),
                key=KEY,
                value_json=value_json,
                description="Seeded by scripts/seed_website_external_links.py",
                status=CommonEnabledStatus.ENABLED.value,
            )
            session.add(cfg)
        else:
            cfg.value_json = value_json
            cfg.status = CommonEnabledStatus.ENABLED.value
            cfg.description = "Updated by scripts/seed_website_external_links.py"
        await session.commit()

    print(f"OK: upserted {KEY} version={value_json.get('version')}")
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(_main())


