"""地区/城市配置（只读，v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> F-1. 城市配置读侧（跨端复用，v1 固化）

说明：
- v1 使用 SystemConfig 作为最小承载；仅提供读侧接口。
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.models.enums import CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["regions"])

_KEY_REGION_CITIES = "REGION_CITIES"


@router.get("/regions/cities")
async def get_region_cities(request: Request):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(
                select(SystemConfig)
                .where(SystemConfig.key == _KEY_REGION_CITIES, SystemConfig.status == CommonEnabledStatus.ENABLED.value)
                .limit(1)
            )
        ).first()

    if cfg is None:
        return ok(data={"items": [], "defaultCode": None, "version": "0"}, request_id=request.state.request_id)

    raw = cfg.value_json or {}
    version = str(raw.get("version") or "0")
    default_code = raw.get("defaultCode")

    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []

    # PROVINCE 可见性映射：用于级联隐藏其下 CITY（避免“隐藏省但市仍可选”的一致性问题）
    province_visible: dict[str, bool] = {}
    for x in items:
        if not isinstance(x, dict):
            continue
        code = str(x.get("code") or "")
        if not code.startswith("PROVINCE:"):
            continue
        if not bool(x.get("enabled")) or not bool(x.get("published")):
            province_visible[code] = False
        else:
            province_visible[code] = True

    out_items: list[dict] = []
    for x in items:
        if not isinstance(x, dict):
            continue
        if not bool(x.get("enabled")):
            continue
        if not bool(x.get("published")):
            continue

        code = str(x.get("code") or "")
        # 级联规则：若 CITY 的所属 PROVINCE 被隐藏/未发布，则 CITY 也不对外可见
        if code.startswith("CITY:"):
            raw6 = code.split(":", 1)[1] if ":" in code else ""
            if raw6.isdigit() and len(raw6) == 6:
                prov_code = f"PROVINCE:{raw6[:2]}0000"
                if prov_code in province_visible and province_visible[prov_code] is False:
                    continue

        out_items.append(
            {
                "code": code,
                "name": str(x.get("name") or ""),
                "sort": int(x.get("sort") or 0),
            }
        )

    out_items.sort(key=lambda i: int(i.get("sort") or 0))

    # defaultCode 必须在 items 中，否则置空（由端侧自行选择默认）
    if default_code is not None:
        default_code = str(default_code)
        if default_code not in {x["code"] for x in out_items}:
            default_code = None

    return ok(data={"items": out_items, "defaultCode": default_code, "version": version}, request_id=request.state.request_id)

