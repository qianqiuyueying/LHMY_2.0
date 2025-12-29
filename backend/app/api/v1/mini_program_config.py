"""小程序配置读侧（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> F. 小程序配置读侧（mini-program，只读已发布/已启用）
- specs/health-services-platform/tasks.md -> 阶段9-53

说明（v1 最小）：
- 规格仅约束对外接口契约（response shape 与只读规则），不约束内部存储实现。
- 本实现采用 SystemConfig（key/valueJson）作为最小承载，便于后续替换为 B2「通用表 + schema」方案。
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.models.system_config import SystemConfig
from app.models.enums import CommonEnabledStatus
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["mini-program-config"])

# v1 最小存储 key（内部实现细节，不对外暴露）
_KEY_ENTRIES = "MINI_PROGRAM_ENTRIES"
_KEY_PAGES = "MINI_PROGRAM_PAGES"
_KEY_COLLECTIONS = "MINI_PROGRAM_COLLECTIONS"
_KEY_HOME_RECOMMENDED_VENUES = "MINI_PROGRAM_HOME_RECOMMENDED_VENUES"
_KEY_HOME_RECOMMENDED_PRODUCTS = "MINI_PROGRAM_HOME_RECOMMENDED_PRODUCTS"


async def _get_enabled_config_value(key: str) -> dict | None:
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


@router.get("/mini-program/home/recommended-venues")
async def mini_program_get_home_recommended_venues(request: Request):
    """小程序首页推荐场所（可运营配置）。

    口径：
    - 若配置未启用/不存在：返回空列表（enabled=false）
    - 仅返回 publish_status=PUBLISHED 的场所
    """
    raw = await _get_enabled_config_value(_KEY_HOME_RECOMMENDED_VENUES)
    if raw is None:
        return ok(data={"enabled": False, "items": [], "version": "0"}, request_id=request.state.request_id)

    version = str(raw.get("version") or "0")
    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []
    venue_ids: list[str] = []
    for x in items:
        if isinstance(x, dict) and x.get("venueId"):
            venue_ids.append(str(x.get("venueId")))
    if not venue_ids:
        return ok(data={"enabled": True, "items": [], "version": version}, request_id=request.state.request_id)

    # 延迟 import：避免循环依赖
    from app.models.venue import Venue  # noqa: WPS433
    from app.models.enums import VenuePublishStatus  # noqa: WPS433

    session_factory = get_session_factory()
    async with session_factory() as session:
        venues = (
            await session.scalars(
                select(Venue).where(Venue.id.in_(venue_ids), Venue.publish_status == VenuePublishStatus.PUBLISHED.value)
            )
        ).all()
    by_id = {v.id: v for v in venues}
    out_items: list[dict] = []
    for vid in venue_ids:
        v = by_id.get(vid)
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
            }
        )

    return ok(data={"enabled": True, "items": out_items, "version": version}, request_id=request.state.request_id)


@router.get("/mini-program/home/recommended-products")
async def mini_program_get_home_recommended_products(request: Request):
    """小程序首页推荐商品（可运营配置）。

    口径：
    - 若配置未启用/不存在：返回空列表（enabled=false）
    - 仅返回 status=ON_SALE 的商品
    """
    raw = await _get_enabled_config_value(_KEY_HOME_RECOMMENDED_PRODUCTS)
    if raw is None:
        return ok(data={"enabled": False, "items": [], "version": "0"}, request_id=request.state.request_id)

    version = str(raw.get("version") or "0")
    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []
    product_ids: list[str] = []
    for x in items:
        if isinstance(x, dict) and x.get("productId"):
            product_ids.append(str(x.get("productId")))
    if not product_ids:
        return ok(data={"enabled": True, "items": [], "version": version}, request_id=request.state.request_id)

    from app.models.product import Product  # noqa: WPS433
    from app.models.enums import ProductStatus, ProductFulfillmentType  # noqa: WPS433

    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(Product).where(
                    Product.id.in_(product_ids),
                    Product.status == ProductStatus.ON_SALE.value,
                    Product.fulfillment_type.in_([ProductFulfillmentType.SERVICE.value, ProductFulfillmentType.PHYSICAL_GOODS.value]),
                )
            )
        ).all()
    by_id = {p.id: p for p in rows}
    out_items: list[dict] = []
    for pid in product_ids:
        p = by_id.get(pid)
        if p is None:
            continue
        out_items.append(
            {
                "id": p.id,
                "title": p.title,
                "fulfillmentType": p.fulfillment_type,
                "coverImageUrl": p.cover_image_url,
                "price": p.price or {},
                "tags": p.tags,
            }
        )

    return ok(data={"enabled": True, "items": out_items, "version": version}, request_id=request.state.request_id)


@router.get("/mini-program/entries")
async def mini_program_get_entries(request: Request):
    # 规格：仅返回“已启用 + 已发布”的入口配置
    raw = await _get_enabled_config_value(_KEY_ENTRIES)
    if raw is None:
        return ok(data={"items": [], "version": "0"}, request_id=request.state.request_id)

    version = str(raw.get("version") or "0")
    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []

    out_items: list[dict] = []
    for x in items:
        if not isinstance(x, dict):
            continue
        if not bool(x.get("enabled")):
            continue
        if not bool(x.get("published")):
            continue
        out_items.append(
            {
                "id": str(x.get("id") or ""),
                "name": str(x.get("name") or ""),
                "iconUrl": x.get("iconUrl"),
                "position": x.get("position"),
                "jumpType": x.get("jumpType"),
                "targetId": str(x.get("targetId") or ""),
                "sort": int(x.get("sort") or 0),
            }
        )

    # 基础排序：sort ASC
    out_items.sort(key=lambda i: int(i.get("sort") or 0))
    return ok(data={"items": out_items, "version": version}, request_id=request.state.request_id)


@router.get("/mini-program/pages/{id}")
async def mini_program_get_page(request: Request, id: str):
    # 规格：仅返回“已发布版本”的页面配置；否则 NOT_FOUND
    raw = await _get_enabled_config_value(_KEY_PAGES)
    if raw is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "页面不存在"})

    pages = raw.get("pages") or {}
    if not isinstance(pages, dict):
        pages = {}

    page = pages.get(id)
    if not isinstance(page, dict) or not bool(page.get("published")):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "页面不存在"})

    page_type = page.get("type")
    if page_type not in ("AGG_PAGE", "INFO_PAGE"):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "页面不存在"})

    return ok(
        data={
            "id": str(page.get("id") or id),
            "type": page_type,
            "config": page.get("config") if isinstance(page.get("config"), dict) else {},
            "version": str(page.get("version") or raw.get("version") or "0"),
        },
        request_id=request.state.request_id,
    )


def _match_region(item: dict, region_level: str | None, region_code: str | None) -> bool:
    if not region_level or not region_code:
        return True
    # v1 最小：约定 item.region 为 { CITY/PROVINCE/COUNTRY: code }，缺失则视为不匹配
    region = item.get("region")
    if not isinstance(region, dict):
        return False
    return str(region.get(str(region_level))) == str(region_code)


def _match_taxonomy(item: dict, taxonomy_id: str | None) -> bool:
    if not taxonomy_id:
        return True
    # v1 最小：约定 item.taxonomyId 或 item.taxonomyIds，缺失则视为不匹配
    if str(item.get("taxonomyId") or "") == str(taxonomy_id):
        return True
    taxonomy_ids = item.get("taxonomyIds")
    if isinstance(taxonomy_ids, list) and any(str(x) == str(taxonomy_id) for x in taxonomy_ids):
        return True
    return False


@router.get("/mini-program/collections/{id}/items")
async def mini_program_get_collection_items(
    request: Request,
    id: str,
    page: int = 1,
    pageSize: int = 20,
    regionLevel: Literal["CITY", "PROVINCE", "COUNTRY"] | None = None,
    regionCode: str | None = None,
    taxonomyId: str | None = None,
):
    # 规格：仅返回“已发布”的 items；否则 NOT_FOUND
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    raw = await _get_enabled_config_value(_KEY_COLLECTIONS)
    if raw is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "集合不存在"})

    collections = raw.get("collections") or {}
    if not isinstance(collections, dict):
        collections = {}

    col = collections.get(id)
    if not isinstance(col, dict) or not bool(col.get("published")):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "集合不存在"})

    items = col.get("items") or []
    if not isinstance(items, list):
        items = []

    # v1 最小过滤：按 regionLevel/regionCode/taxonomyId
    filtered: list[Any] = []
    for x in items:
        if not isinstance(x, dict):
            continue
        if not _match_region(x, region_level=str(regionLevel) if regionLevel else None, region_code=regionCode):
            continue
        if not _match_taxonomy(x, taxonomy_id=taxonomyId):
            continue
        filtered.append(x)

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]

    return ok(
        data={"items": page_items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )
