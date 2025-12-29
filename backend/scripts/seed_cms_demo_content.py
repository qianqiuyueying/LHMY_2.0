"""
Seed minimal CMS channels + published contents for website/h5/mini-program read-side.

用途：
- 满足 website 的“内容中心可用”最小数据门槛：至少 1 栏目 + 至少 5 内容 + 至少 1 可阅读详情（contentHtml 非空）。

运行方式（docker compose 环境）：
  docker compose exec backend sh -lc "PYTHONPATH=/app /app/.venv/bin/python /app/scripts/seed_cms_demo_content.py"
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

from app.models.cms_channel import CmsChannel
from app.models.cms_content import CmsContent
from app.models.enums import CmsContentStatus, CommonEnabledStatus
from app.utils.db import get_engine, get_session_factory


async def _ensure_channel(session, *, name: str, sort: int) -> CmsChannel:
    ch = (await session.scalars(select(CmsChannel).where(CmsChannel.name == name).limit(1))).first()
    if ch is not None:
        ch.sort = sort
        ch.status = CommonEnabledStatus.ENABLED.value
        return ch

    ch = CmsChannel(
        id=str(uuid4()),
        name=name,
        sort=sort,
        status=CommonEnabledStatus.ENABLED.value,
    )
    session.add(ch)
    return ch


def _demo_html(title: str) -> str:
    # 仅用简单 HTML（无外部图片）
    return f"""
<h2>{title}</h2>
<p>这是一条用于联调与回归的 DEMO 内容（不包含外部图片）。</p>
<ul>
  <li>可信赖：信息结构清晰</li>
  <li>健康活力：主色系偏青绿</li>
  <li>现代简洁：留白与卡片分组</li>
</ul>
""".strip()


async def _main() -> None:
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 栏目：至少 1 个（建议用“公告”以匹配前端优先级排序）
        ch_notice = await _ensure_channel(session, name="公告", sort=1)

        # 内容：至少 5 条，且至少 1 条具备完整正文
        # 为避免重复写入：以固定 title 前缀识别
        existing = (
            await session.scalars(
                select(CmsContent)
                .where(CmsContent.channel_id == ch_notice.id, CmsContent.title.like("DEMO%"))
                .limit(10)
            )
        ).all()
        if existing:
            print(f"SKIP: demo contents already exist ({len(existing)})")
        else:
            for i in range(1, 6):
                title = f"DEMO 公告 {i}"
                c = CmsContent(
                    id=str(uuid4()),
                    channel_id=ch_notice.id,
                    title=title,
                    cover_image_url=None,
                    summary=f"这是第 {i} 条 DEMO 公告摘要，用于官网内容中心展示。",
                    content_html=_demo_html(title),
                    status=CmsContentStatus.PUBLISHED.value,
                    published_at=now,
                    effective_from=None,
                    effective_until=None,
                )
                session.add(c)

        await session.commit()

    print("OK: seeded cms demo channels/contents")
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(_main())


