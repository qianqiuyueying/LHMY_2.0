"""Website 只读配置下发（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> I. Website 只读配置下发（v1 最小契约）
- specs/health-services-platform/design.md -> SystemConfig key 约定（WEBSITE_*）
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.models.enums import CommonEnabledStatus, VenuePublishStatus
from app.models.system_config import SystemConfig
from app.models.venue import Venue
from app.utils.db import get_session_factory
from app.utils.response import fail, ok

router = APIRouter(tags=["website-config"])

_KEY_RECOMMENDED_VENUES = "WEBSITE_HOME_RECOMMENDED_VENUES"
_KEY_FOOTER_CONFIG = "WEBSITE_FOOTER_CONFIG"
_KEY_EXTERNAL_LINKS = "WEBSITE_EXTERNAL_LINKS"
_KEY_SITE_SEO = "WEBSITE_SITE_SEO"
_KEY_NAV_CONTROL = "WEBSITE_NAV_CONTROL"
_KEY_MAINTENANCE_MODE = "WEBSITE_MAINTENANCE_MODE"


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


async def _get_enabled_value(key: str) -> dict | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(
                select(SystemConfig)
                .where(SystemConfig.key == key, SystemConfig.status == CommonEnabledStatus.ENABLED.value)
                .limit(1)
            )
        ).first()
    if cfg is None:
        return None
    return cfg.value_json or {}


@router.get("/website/home/recommended-venues")
async def website_get_recommended_venues(request: Request):
    raw = await _get_enabled_value(_KEY_RECOMMENDED_VENUES)
    if raw is None:
        return ok(data={"items": [], "version": "0"}, request_id=request.state.request_id)

    version = str(raw.get("version") or "0")
    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []

    venue_ids: list[str] = []
    for x in items:
        if isinstance(x, dict) and x.get("venueId"):
            venue_ids.append(str(x.get("venueId")))

    if not venue_ids:
        return ok(data={"items": [], "version": version}, request_id=request.state.request_id)

    session_factory = get_session_factory()
    async with session_factory() as session:
        venues = (
            await session.scalars(
                select(Venue).where(
                    Venue.id.in_(venue_ids),
                    Venue.publish_status == VenuePublishStatus.PUBLISHED.value,
                )
            )
        ).all()

    venue_map = {v.id: v for v in venues}
    out_items: list[dict] = []
    for vid in venue_ids:
        v = venue_map.get(vid)
        if v is None:
            continue
        out_items.append(
            {
                "id": v.id,
                "name": v.name,
                "coverImageUrl": getattr(v, "cover_image_url", None),
                "cityCode": v.city_code,
                "provinceCode": v.province_code,
                "countryCode": v.country_code,
                "address": v.address,
                "tags": v.tags,
                "contactPhoneMasked": _mask_phone(v.contact_phone),
            }
        )

    return ok(data={"items": out_items, "version": version}, request_id=request.state.request_id)


@router.get("/website/footer/config")
async def website_get_footer_config(request: Request):
    raw = await _get_enabled_value(_KEY_FOOTER_CONFIG)
    if raw is None:
        # 已确认契约（specs/功能实现/website/api-contracts.md）：data 直接为 FooterConfig；
        # 若未配置，必须返回可区分的业务错误，避免前端静默展示“—”造成假可用。
        return fail(
            code="WEBSITE_FOOTER_CONFIG_MISSING",
            message="官网页脚信息未配置",
            request_id=request.state.request_id,
        )

    # 方案 A：data 直接是 FooterConfig（不再额外包一层 config/version）
    # 注意：FooterConfig 允许包含 version 字段（来自 SystemConfig.valueJson）。
    return ok(data=raw, request_id=request.state.request_id)


@router.get("/website/external-links")
async def website_get_external_links(request: Request):
    raw = await _get_enabled_value(_KEY_EXTERNAL_LINKS)
    if raw is None:
        return fail(
            code="WEBSITE_EXTERNAL_LINKS_MISSING",
            message="官网导流外链未配置",
            request_id=request.state.request_id,
        )

    mini = str(raw.get("miniProgramUrl") or "").strip()
    h5 = str(raw.get("h5BuyUrl") or "").strip()
    if not mini or not h5:
        return fail(
            code="WEBSITE_EXTERNAL_LINKS_INVALID",
            message="官网导流外链配置不完整",
            request_id=request.state.request_id,
        )

    return ok(
        data={
            "miniProgramUrl": mini,
            "h5BuyUrl": h5,
            "version": str(raw.get("version") or "0"),
        },
        request_id=request.state.request_id,
    )


@router.get("/website/site-seo")
async def website_get_site_seo(request: Request):
    raw = await _get_enabled_value(_KEY_SITE_SEO)
    if raw is None:
        return ok(
            data={
                "siteName": "陆合铭云健康服务平台",
                "defaultTitle": "陆合铭云健康服务平台",
                "defaultDescription": "统一入口 · 多业务线协同 · 可信赖服务",
                "canonicalBaseUrl": "",
                "robots": "index,follow",
                "version": "0",
            },
            request_id=request.state.request_id,
        )
    return ok(data=raw, request_id=request.state.request_id)


@router.get("/website/nav-control")
async def website_get_nav_control(request: Request):
    raw = await _get_enabled_value(_KEY_NAV_CONTROL)
    if raw is None:
        return ok(
            data={
                "navItems": {
                    "home": {"enabled": True},
                    "business": {"enabled": True},
                    "venues": {"enabled": True},
                    "content": {"enabled": True},
                    "about": {"enabled": True},
                    "contact": {"enabled": True},
                },
                "version": "0",
            },
            request_id=request.state.request_id,
        )
    return ok(data=raw, request_id=request.state.request_id)


@router.get("/website/maintenance-mode")
async def website_get_maintenance_mode(request: Request):
    raw = await _get_enabled_value(_KEY_MAINTENANCE_MODE)
    if raw is None:
        return ok(
            data={
                "enabled": False,
                "messageTitle": "维护中",
                "messageBody": "我们正在进行系统维护，请稍后再试。",
                "allowPaths": [],
                "allowIps": [],
                "version": "0",
            },
            request_id=request.state.request_id,
        )
    return ok(data=raw, request_id=request.state.request_id)

