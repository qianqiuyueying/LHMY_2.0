"""
Seed / upsert WEBSITE_FOOTER_CONFIG into SystemConfig.

用途：
- 让 website 页脚在部署环境具备最小可用信息（公司名/邮箱/电话），避免“全是—”或缺失错误导致不可用。

运行方式（在 docker compose 环境）：
- demo（写入演示值）：docker compose exec backend python scripts/seed_website_footer_config.py --demo
- 显式传参：docker compose exec backend python scripts/seed_website_footer_config.py --company-name "xxx" --email "a@b.com" --phone "123"
- 或通过环境变量提供：
  - WEBSITE_FOOTER_COMPANY_NAME / WEBSITE_FOOTER_COOP_EMAIL / WEBSITE_FOOTER_COOP_PHONE
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from uuid import uuid4

# 允许脚本以 “python scripts/xxx.py” 方式运行（sys.path[0] 会指向 scripts/ 目录）
# 这里显式把项目根目录（/app）加入 sys.path，确保可 import app.*
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import select

from app.models.enums import CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.utils.db import get_engine, get_session_factory


KEY = "WEBSITE_FOOTER_CONFIG"


def _now_version() -> str:
    return str(int(time.time()))


def _build_value(
    *,
    demo: bool,
    company_name: str | None,
    email: str | None,
    phone: str | None,
    icp_no: str | None,
    icp_link: str | None,
    public_qr_url: str | None,
    mini_qr_url: str | None,
) -> dict:
    if demo:
        return {
            "version": _now_version(),
            "companyName": "陆合铭云健康服务平台（DEMO）",
            "cooperationEmail": "bd@example.com",
            "cooperationPhone": "400-000-0000",
            "icpBeianNo": "",
            "icpBeianLink": "",
            "publicAccountQrUrl": "",
            "miniProgramQrUrl": "",
        }

    if not (company_name and company_name.strip()):
        raise SystemExit("缺少 --company-name 或 WEBSITE_FOOTER_COMPANY_NAME")
    if not (email and email.strip()):
        raise SystemExit("缺少 --email 或 WEBSITE_FOOTER_COOP_EMAIL")
    if not (phone and phone.strip()):
        raise SystemExit("缺少 --phone 或 WEBSITE_FOOTER_COOP_PHONE")

    out = {
        "version": _now_version(),
        "companyName": company_name.strip(),
        "cooperationEmail": email.strip(),
        "cooperationPhone": phone.strip(),
    }
    if icp_no is not None:
        out["icpBeianNo"] = icp_no.strip()
    if icp_link is not None:
        out["icpBeianLink"] = icp_link.strip()
    if public_qr_url is not None:
        out["publicAccountQrUrl"] = public_qr_url.strip()
    if mini_qr_url is not None:
        out["miniProgramQrUrl"] = mini_qr_url.strip()
    return out


async def _main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true", help="写入演示值（用于本地联调/回归）")
    p.add_argument("--company-name", dest="company_name")
    p.add_argument("--email")
    p.add_argument("--phone")
    p.add_argument("--icp-no", dest="icp_no")
    p.add_argument("--icp-link", dest="icp_link")
    p.add_argument("--public-qr-url", dest="public_qr_url")
    p.add_argument("--mini-qr-url", dest="mini_qr_url")
    args = p.parse_args()

    # 环境变量兜底（仅在未传参时使用）
    import os

    company_name = args.company_name or os.getenv("WEBSITE_FOOTER_COMPANY_NAME")
    email = args.email or os.getenv("WEBSITE_FOOTER_COOP_EMAIL")
    phone = args.phone or os.getenv("WEBSITE_FOOTER_COOP_PHONE")

    value_json = _build_value(
        demo=bool(args.demo),
        company_name=company_name,
        email=email,
        phone=phone,
        icp_no=args.icp_no,
        icp_link=args.icp_link,
        public_qr_url=args.public_qr_url,
        mini_qr_url=args.mini_qr_url,
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == KEY).limit(1))).first()
        if cfg is None:
            cfg = SystemConfig(
                id=str(uuid4()),
                key=KEY,
                value_json=value_json,
                description="Seeded by scripts/seed_website_footer_config.py",
                status=CommonEnabledStatus.ENABLED.value,
            )
            session.add(cfg)
        else:
            cfg.value_json = value_json
            cfg.status = CommonEnabledStatus.ENABLED.value
            cfg.description = "Updated by scripts/seed_website_footer_config.py"

        await session.commit()

    print(f"OK: upserted {KEY} version={value_json.get('version')}")
    # 主动释放连接池，避免脚本退出时触发 “Event loop is closed” 的清理警告
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(_main())


