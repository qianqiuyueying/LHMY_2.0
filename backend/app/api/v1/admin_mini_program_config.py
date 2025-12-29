"""Admin 小程序配置中心（v1 最小可执行）。

规格来源（已确认）：
- specs/health-services-platform/tasks.md -> 阶段9-54「规格补充（待确认）」（用户已确认采用）

提供接口（v1 最小）：
- GET  /api/v1/admin/mini-program/entries
- PUT  /api/v1/admin/mini-program/entries
- POST /api/v1/admin/mini-program/entries/publish
- POST /api/v1/admin/mini-program/entries/offline

- GET  /api/v1/admin/mini-program/pages
- PUT  /api/v1/admin/mini-program/pages/{id}
- POST /api/v1/admin/mini-program/pages/{id}/publish
- POST /api/v1/admin/mini-program/pages/{id}/offline

- GET  /api/v1/admin/mini-program/collections
- PUT  /api/v1/admin/mini-program/collections/{id}
- POST /api/v1/admin/mini-program/collections/{id}/publish
- POST /api/v1/admin/mini-program/collections/{id}/offline

存储承载（实现细节）：
- SystemConfig.key：MINI_PROGRAM_ENTRIES / MINI_PROGRAM_PAGES / MINI_PROGRAM_COLLECTIONS
"""

from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType, CommonEnabledStatus
from app.models.enums import ProductStatus, VenuePublishStatus
from app.models.product import Product
from app.models.system_config import SystemConfig
from app.models.venue import Venue
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.settings import settings
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-mini-program-config"])

_KEY_ENTRIES = "MINI_PROGRAM_ENTRIES"
_KEY_PAGES = "MINI_PROGRAM_PAGES"
_KEY_COLLECTIONS = "MINI_PROGRAM_COLLECTIONS"
_KEY_HOME_RECOMMENDED_VENUES = "MINI_PROGRAM_HOME_RECOMMENDED_VENUES"
_KEY_HOME_RECOMMENDED_PRODUCTS = "MINI_PROGRAM_HOME_RECOMMENDED_PRODUCTS"


def _ensure_json_serializable(value: Any, *, field_name: str) -> None:
    """REQ-P2-006：配置验证与格式化（最小）。

    口径：
    - 只做“能否序列化为 JSON”的校验，避免写入不可序列化对象导致后续读侧异常。
    - 不改变接口返回结构；仅在写入前拒绝非法配置。
    """

    try:
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 不是合法 JSON"},
        ) from exc


def _now_version() -> str:
    # v1：最小可用版本号（字符串），用于读侧缓存/比对
    return str(int(time.time()))


def _audit_mini_program_config(
    *,
    request: Request,
    admin_id: str,
    action: str,
    resource_id: str,
    meta: dict[str, Any] | None = None,
) -> AuditLog:
    return AuditLog(
        id=str(uuid4()),
        actor_type=AuditActorType.ADMIN.value,
        actor_id=admin_id,
        action=action,
        resource_type="MINI_PROGRAM_CONFIG",
        resource_id=resource_id,
        summary=f"ADMIN 更新小程序配置：{resource_id}",
        ip=getattr(getattr(request, "client", None), "host", None),
        user_agent=request.headers.get("User-Agent"),
        metadata_json={
            "path": request.url.path,
            "method": request.method,
            "requestId": request.state.request_id,
            **(meta or {}),
        },
    )


async def _get_or_create_config(session, key: str) -> SystemConfig:
    cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == key).limit(1))).first()
    if cfg is not None:
        return cfg

    cfg = SystemConfig(
        id=str(uuid4()),
        key=key,
        value_json={},
        description=f"Auto-created by admin mini program config for {key}",
        status=CommonEnabledStatus.ENABLED.value,
    )
    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)
    return cfg


def _set_value_json(cfg: SystemConfig, value: dict) -> None:
    """确保 JSON 字段变更能被 SQLAlchemy 追踪并落库。

    背景：MySQL JSON 字段默认不会追踪 dict 的就地变更；若直接复用同一个 dict 对象，
    可能出现“接口 200 但刷新后数据没变”的假象（运营侧体验灾难）。
    """

    cfg.value_json = deepcopy(value or {})
    flag_modified(cfg, "value_json")


# -----------------------------
# home recommendations (venues/products)
# -----------------------------


class RecommendedVenueItem(BaseModel):
    venueId: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _trim(self):
        self.venueId = str(self.venueId or "").strip()
        if not self.venueId:
            raise ValueError("venueId 不能为空")
        return self


class PutHomeRecommendedVenuesBody(BaseModel):
    enabled: bool = True
    items: list[RecommendedVenueItem] = Field(default_factory=list)
    version: str | None = None


@router.get("/admin/mini-program/home/recommended-venues")
async def admin_get_mp_home_recommended_venues(request: Request, _admin=Depends(require_admin)):
    _ = _admin
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_HOME_RECOMMENDED_VENUES).limit(1))
        ).first()
        raw = cfg.value_json if cfg else None
        enabled = (cfg.status == CommonEnabledStatus.ENABLED.value) if cfg else False

        version = "0"
        items = []
        if isinstance(raw, dict):
            version = str(raw.get("version") or "0")
            items = raw.get("items") or []

        venue_ids: list[str] = []
        for x in items:
            if isinstance(x, dict) and x.get("venueId"):
                venue_ids.append(str(x.get("venueId")))

        venues = (await session.scalars(select(Venue).where(Venue.id.in_(venue_ids)))).all() if venue_ids else []
        by_id = {v.id: v for v in venues}

    out_items: list[dict] = []
    for vid in venue_ids:
        v = by_id.get(vid)
        out_items.append(
            {
                "venueId": vid,
                "name": v.name if v else "",
                "publishStatus": v.publish_status if v else "NOT_FOUND",
            }
        )
    return ok(data={"enabled": enabled, "items": out_items, "version": version}, request_id=request.state.request_id)


@router.put("/admin/mini-program/home/recommended-venues")
async def admin_put_mp_home_recommended_venues(
    request: Request, body: PutHomeRecommendedVenuesBody, _admin: ActorContext = Depends(require_admin_phone_bound)
):
    _ensure_json_serializable(body.model_dump(), field_name="body")
    admin_id = str(_admin.sub)

    venue_ids = [x.venueId for x in (body.items or [])]
    seen: set[str] = set()
    for vid in venue_ids:
        if vid in seen:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"重复的 venueId：{vid}"})
        seen.add(vid)

    session_factory = get_session_factory()
    async with session_factory() as session:
        if venue_ids:
            venues = (await session.scalars(select(Venue).where(Venue.id.in_(venue_ids)))).all()
            by_id = {v.id: v for v in venues}
            for vid in venue_ids:
                v = by_id.get(vid)
                if v is None:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"场所不存在：{vid}"})
                if v.publish_status != VenuePublishStatus.PUBLISHED.value:
                    raise HTTPException(
                        status_code=400,
                        detail={"code": "INVALID_ARGUMENT", "message": f"场所未发布，不能推荐：{vid}（{v.publish_status}）"},
                    )

        cfg = await _get_or_create_config(session, _KEY_HOME_RECOMMENDED_VENUES)
        before_version = str((cfg.value_json or {}).get("version") or "0")
        value = {"version": _now_version(), "items": [{"venueId": x} for x in venue_ids]}
        _set_value_json(cfg, value)
        cfg.status = CommonEnabledStatus.ENABLED.value if body.enabled else CommonEnabledStatus.DISABLED.value
        session.add(
            _audit_mini_program_config(
                request=request,
                admin_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_id=_KEY_HOME_RECOMMENDED_VENUES,
                meta={"key": _KEY_HOME_RECOMMENDED_VENUES, "beforeVersion": before_version, "afterVersion": value["version"]},
            )
        )
        await session.commit()

    value["enabled"] = body.enabled
    return ok(data=value, request_id=request.state.request_id)


class RecommendedProductItem(BaseModel):
    productId: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _trim(self):
        self.productId = str(self.productId or "").strip()
        if not self.productId:
            raise ValueError("productId 不能为空")
        return self


class PutHomeRecommendedProductsBody(BaseModel):
    enabled: bool = True
    items: list[RecommendedProductItem] = Field(default_factory=list)
    version: str | None = None


@router.get("/admin/mini-program/home/recommended-products")
async def admin_get_mp_home_recommended_products(request: Request, _admin=Depends(require_admin)):
    _ = _admin
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_HOME_RECOMMENDED_PRODUCTS).limit(1))
        ).first()
        raw = cfg.value_json if cfg else None
        enabled = (cfg.status == CommonEnabledStatus.ENABLED.value) if cfg else False

        version = "0"
        items = []
        if isinstance(raw, dict):
            version = str(raw.get("version") or "0")
            items = raw.get("items") or []

        product_ids: list[str] = []
        for x in items:
            if isinstance(x, dict) and x.get("productId"):
                product_ids.append(str(x.get("productId")))

        products = (await session.scalars(select(Product).where(Product.id.in_(product_ids)))).all() if product_ids else []
        by_id = {p.id: p for p in products}

    out_items: list[dict] = []
    for pid in product_ids:
        p = by_id.get(pid)
        out_items.append(
            {
                "productId": pid,
                "title": p.title if p else "",
                "status": p.status if p else "NOT_FOUND",
            }
        )
    return ok(data={"enabled": enabled, "items": out_items, "version": version}, request_id=request.state.request_id)


@router.put("/admin/mini-program/home/recommended-products")
async def admin_put_mp_home_recommended_products(
    request: Request, body: PutHomeRecommendedProductsBody, _admin: ActorContext = Depends(require_admin_phone_bound)
):
    _ensure_json_serializable(body.model_dump(), field_name="body")
    admin_id = str(_admin.sub)

    product_ids = [x.productId for x in (body.items or [])]
    seen: set[str] = set()
    for pid in product_ids:
        if pid in seen:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"重复的 productId：{pid}"})
        seen.add(pid)

    session_factory = get_session_factory()
    async with session_factory() as session:
        if product_ids:
            products = (await session.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
            by_id = {p.id: p for p in products}
            for pid in product_ids:
                p = by_id.get(pid)
                if p is None:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"商品不存在：{pid}"})
                if p.status != ProductStatus.ON_SALE.value:
                    raise HTTPException(
                        status_code=400,
                        detail={"code": "INVALID_ARGUMENT", "message": f"商品未上架，不能推荐：{pid}（{p.status}）"},
                    )

        cfg = await _get_or_create_config(session, _KEY_HOME_RECOMMENDED_PRODUCTS)
        before_version = str((cfg.value_json or {}).get("version") or "0")
        value = {"version": _now_version(), "items": [{"productId": x} for x in product_ids]}
        _set_value_json(cfg, value)
        cfg.status = CommonEnabledStatus.ENABLED.value if body.enabled else CommonEnabledStatus.DISABLED.value
        session.add(
            _audit_mini_program_config(
                request=request,
                admin_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_id=_KEY_HOME_RECOMMENDED_PRODUCTS,
                meta={"key": _KEY_HOME_RECOMMENDED_PRODUCTS, "beforeVersion": before_version, "afterVersion": value["version"]},
            )
        )
        await session.commit()

    value["enabled"] = body.enabled
    return ok(data=value, request_id=request.state.request_id)


# -----------------------------
# entries
# -----------------------------


class AdminEntryItem(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    iconUrl: str | None = None
    position: Literal["SHORTCUT", "OPERATION"]
    jumpType: Literal["AGG_PAGE", "INFO_PAGE", "WEBVIEW", "ROUTE", "MINI_PROGRAM"]
    targetId: str = Field(..., min_length=1)
    sort: int = 0
    enabled: bool = True
    # 注意：published 由 publish/offline 控制；PUT 会忽略该字段
    published: bool | None = None

    @model_validator(mode="after")
    def _validate_webview_target_id(self):
        if self.jumpType != "WEBVIEW":
            return self

        url = str(self.targetId or "").strip()
        if not url:
            raise ValueError("targetId 不能为空")

        # v1 固化：
        # - 生产：只允许 https://
        # - 开发：允许 http://localhost（或本地回环）
        env = str(getattr(settings, "app_env", "") or "").lower()
        if env == "production":
            if not url.startswith("https://"):
                raise ValueError("WEBVIEW 的 targetId 必须为 https:// URL（生产环境）")
            return self

        allowed_dev_prefixes = ("https://", "http://localhost", "http://127.0.0.1", "http://0.0.0.0")
        if not url.startswith(allowed_dev_prefixes):
            raise ValueError("WEBVIEW 的 targetId 必须为 https:// 或本地回环 URL（开发环境）")
        return self

    @model_validator(mode="after")
    def _validate_mini_program_target_id(self):
        if self.jumpType != "MINI_PROGRAM":
            return self
        # vNow：targetId 约定为 "appid|path"（path 可为空）
        raw = str(self.targetId or "").strip()
        if not raw:
            raise ValueError("targetId 不能为空")
        if "|" not in raw:
            raise ValueError("MINI_PROGRAM 的 targetId 必须为 appid|path（例如 wx123...|/pages/index/index）")
        appid, path = raw.split("|", 1)
        appid = appid.strip()
        path = path.strip()
        if not appid:
            raise ValueError("MINI_PROGRAM 的 appid 不能为空")
        # path 允许为空；若不为空则应以 / 开头（小程序 path 口径）
        if path and not path.startswith("/"):
            raise ValueError("MINI_PROGRAM 的 path 必须以 / 开头（例如 /pages/index/index）")
        return self


class AdminPutEntriesBody(BaseModel):
    items: list[AdminEntryItem]
    version: str | None = None


@router.get("/admin/mini-program/entries")
async def admin_get_entries(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_ENTRIES).limit(1))).first()
    if cfg is None:
        return ok(data={"items": [], "version": "0"}, request_id=request.state.request_id)

    raw = cfg.value_json or {}
    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []
    version = str(raw.get("version") or "0")
    return ok(data={"items": items, "version": version}, request_id=request.state.request_id)


@router.put("/admin/mini-program/entries")
async def admin_put_entries(
    request: Request, body: AdminPutEntriesBody, _admin=Depends(require_admin)
):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_ENTRIES)
        raw = cfg.value_json or {}
        existing_items = raw.get("items") or []
        if not isinstance(existing_items, list):
            existing_items = []

        # 保留已存在 published 状态：以 id 作为主键
        published_by_id: dict[str, bool] = {}
        for x in existing_items:
            if isinstance(x, dict) and x.get("id"):
                published_by_id[str(x.get("id"))] = bool(x.get("published"))

        new_items: list[dict] = []
        for x in body.items:
            d = x.model_dump()
            item_id = str(d.get("id") or "")
            d["published"] = bool(published_by_id.get(item_id, False))
            new_items.append(d)

        raw["items"] = new_items
        # PUT 仅更新草稿：不改 version（version 由 publish/offline 写入）；允许透传 version 但不作为发布版本
        if body.version is not None:
            raw.setdefault("draftVersion", str(body.version))

        _ensure_json_serializable(raw, field_name="entries")
        _set_value_json(cfg, raw)
        await session.commit()

    return ok(
        data={"items": new_items, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )


@router.post("/admin/mini-program/entries/publish")
async def admin_publish_entries(request: Request, _admin: ActorContext = Depends(require_admin_phone_bound)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_ENTRIES)
        raw = cfg.value_json or {}
        items = raw.get("items") or []
        if not isinstance(items, list):
            items = []

        # 幂等 no-op：已全部 published=True 则不推进 version、不写审计
        if all((isinstance(x, dict) and bool(x.get("published")) is True) for x in items):
            return ok(
                data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
                request_id=request.state.request_id,
            )

        for x in items:
            if isinstance(x, dict):
                x["published"] = True
        raw["items"] = items
        raw["version"] = _now_version()
        _ensure_json_serializable(raw, field_name="entries")
        _set_value_json(cfg, raw)
        session.add(
            _audit_mini_program_config(
                request=request,
                admin_id=str(_admin.sub),
                action=AuditAction.PUBLISH.value,
                resource_id="ENTRIES",
                meta={"key": _KEY_ENTRIES, "afterPublished": True},
            )
        )
        await session.commit()

    return ok(
        data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )


@router.post("/admin/mini-program/entries/offline")
async def admin_offline_entries(request: Request, _admin: ActorContext = Depends(require_admin_phone_bound)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_ENTRIES)
        raw = cfg.value_json or {}
        items = raw.get("items") or []
        if not isinstance(items, list):
            items = []

        if all((isinstance(x, dict) and bool(x.get("published")) is False) for x in items):
            return ok(
                data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
                request_id=request.state.request_id,
            )

        for x in items:
            if isinstance(x, dict):
                x["published"] = False
        raw["items"] = items
        raw["version"] = _now_version()
        _ensure_json_serializable(raw, field_name="entries")
        _set_value_json(cfg, raw)
        session.add(
            _audit_mini_program_config(
                request=request,
                admin_id=str(_admin.sub),
                action=AuditAction.OFFLINE.value,
                resource_id="ENTRIES",
                meta={"key": _KEY_ENTRIES, "afterPublished": False},
            )
        )
        await session.commit()

    return ok(
        data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )


# -----------------------------
# pages
# -----------------------------


class AdminPageItem(BaseModel):
    id: str = Field(..., min_length=1)
    type: Literal["AGG_PAGE", "INFO_PAGE"]
    config: dict[str, Any] = Field(default_factory=dict)
    version: str | None = None
    published: bool = False
    # 回显：草稿/发布状态（REQ-ADMIN-P0-012：预览与回显）
    draftVersion: str | None = None
    draftUpdatedAt: str | None = None
    publishedAt: str | None = None


@router.get("/admin/mini-program/pages")
async def admin_get_pages(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_PAGES).limit(1))).first()
    if cfg is None:
        return ok(data={"items": [], "version": "0"}, request_id=request.state.request_id)

    raw = cfg.value_json or {}
    pages = raw.get("pages") or {}
    if not isinstance(pages, dict):
        pages = {}
    version = str(raw.get("version") or "0")

    items: list[dict] = []
    for _id, v in pages.items():
        if not isinstance(v, dict):
            continue
        items.append(
            {
                "id": str(v.get("id") or _id),
                "type": v.get("type"),
                "config": v.get("config") if isinstance(v.get("config"), dict) else {},
                "version": str(v.get("version") or version),
                "published": bool(v.get("published")),
                "draftVersion": str(v.get("draftVersion")) if v.get("draftVersion") is not None else None,
                "draftUpdatedAt": str(v.get("draftUpdatedAt")) if v.get("draftUpdatedAt") is not None else None,
                "publishedAt": str(v.get("publishedAt")) if v.get("publishedAt") is not None else None,
            }
        )

    return ok(data={"items": items, "version": version}, request_id=request.state.request_id)


class AdminPutPageBody(BaseModel):
    type: Literal["AGG_PAGE", "INFO_PAGE"] | None = None
    config: dict[str, Any] | None = None
    published: bool | None = None
    version: str | None = None


@router.put("/admin/mini-program/pages/{id}")
async def admin_put_page(
    request: Request,
    id: str,
    body: AdminPutPageBody,
    _admin=Depends(require_admin),
):
    # 规格：published 只能通过 publish/offline 控制
    if body.published is not None:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "published 不允许通过该接口修改"}
        )

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_PAGES)
        raw = cfg.value_json or {}
        pages = raw.get("pages") or {}
        if not isinstance(pages, dict):
            pages = {}

        page = pages.get(id)
        if not isinstance(page, dict):
            page = {"id": id, "type": "INFO_PAGE", "config": {}, "published": False}

        if body.type is not None:
            page["type"] = str(body.type)
        if body.config is not None:
            page["config"] = body.config if isinstance(body.config, dict) else {}
        # 草稿：每次保存都更新时间戳/草稿版本，便于运营识别“草稿态”
        now = datetime.now()
        page["draftUpdatedAt"] = _iso(now)
        page["draftVersion"] = str(body.version) if body.version is not None else _now_version()

        pages[id] = page
        raw["pages"] = pages
        _ensure_json_serializable(raw, field_name="pages")
        _set_value_json(cfg, raw)
        await session.commit()

    return ok(
        data={
            "id": str(page.get("id") or id),
            "type": page.get("type"),
            "config": page.get("config") if isinstance(page.get("config"), dict) else {},
            "version": str(page.get("version") or raw.get("version") or "0"),
            "published": bool(page.get("published")),
            "draftVersion": str(page.get("draftVersion")) if page.get("draftVersion") is not None else None,
            "draftUpdatedAt": str(page.get("draftUpdatedAt")) if page.get("draftUpdatedAt") is not None else None,
            "publishedAt": str(page.get("publishedAt")) if page.get("publishedAt") is not None else None,
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/mini-program/pages/{id}/publish")
async def admin_publish_page(request: Request, id: str, _admin: ActorContext = Depends(require_admin_phone_bound)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_PAGES)
        raw = cfg.value_json or {}
        pages = raw.get("pages") or {}
        if not isinstance(pages, dict):
            pages = {}

        page = pages.get(id)
        if not isinstance(page, dict):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "页面不存在"})

        if bool(page.get("published")) is True:
            return ok(
                data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
                request_id=request.state.request_id,
            )

        v = _now_version()
        now = datetime.now()
        page["published"] = True
        page["version"] = v
        page["publishedAt"] = _iso(now)
        # 发布后草稿视为已同步（无待发布变更）
        page["draftVersion"] = v
        page["draftUpdatedAt"] = _iso(now)
        pages[id] = page
        raw["pages"] = pages
        raw["version"] = v
        _ensure_json_serializable(raw, field_name="pages")
        _set_value_json(cfg, raw)
        session.add(
            _audit_mini_program_config(
                request=request,
                admin_id=str(_admin.sub),
                action=AuditAction.PUBLISH.value,
                resource_id=f"PAGES:{id}",
                meta={"key": _KEY_PAGES, "pageId": id, "afterPublished": True},
            )
        )
        await session.commit()

    return ok(
        data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )


@router.post("/admin/mini-program/pages/{id}/offline")
async def admin_offline_page(request: Request, id: str, _admin: ActorContext = Depends(require_admin_phone_bound)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_PAGES)
        raw = cfg.value_json or {}
        pages = raw.get("pages") or {}
        if not isinstance(pages, dict):
            pages = {}

        page = pages.get(id)
        if not isinstance(page, dict):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "页面不存在"})

        if bool(page.get("published")) is False:
            return ok(
                data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
                request_id=request.state.request_id,
            )

        v = _now_version()
        page["published"] = False
        page["version"] = v
        pages[id] = page
        raw["pages"] = pages
        raw["version"] = v
        _ensure_json_serializable(raw, field_name="pages")
        _set_value_json(cfg, raw)
        session.add(
            _audit_mini_program_config(
                request=request,
                admin_id=str(_admin.sub),
                action=AuditAction.OFFLINE.value,
                resource_id=f"PAGES:{id}",
                meta={"key": _KEY_PAGES, "pageId": id, "afterPublished": False},
            )
        )
        await session.commit()

    return ok(
        data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )


# -----------------------------
# collections
# -----------------------------


@router.get("/admin/mini-program/collections")
async def admin_get_collections(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_COLLECTIONS).limit(1))).first()
    if cfg is None:
        return ok(data={"items": [], "version": "0"}, request_id=request.state.request_id)

    raw = cfg.value_json or {}
    cols = raw.get("collections") or {}
    if not isinstance(cols, dict):
        cols = {}
    version = str(raw.get("version") or "0")

    items: list[dict] = []
    for _id, v in cols.items():
        if not isinstance(v, dict):
            continue
        items.append(
            {
                "id": str(v.get("id") or _id),
                "name": str(v.get("name") or ""),
                "published": bool(v.get("published")),
                "updatedAt": v.get("updatedAt"),
            }
        )

    return ok(data={"items": items, "version": version}, request_id=request.state.request_id)


class AdminPutCollectionBody(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    # 避免与 BaseModel.schema() 命名冲突
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    items: list[Any] | None = None
    published: bool | None = None


@router.put("/admin/mini-program/collections/{id}")
async def admin_put_collection(
    request: Request,
    id: str,
    body: AdminPutCollectionBody,
    _admin=Depends(require_admin),
):
    # 规格：published 只能通过 publish/offline 控制
    if body.published is not None:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "published 不允许通过该接口修改"}
        )

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_COLLECTIONS)
        raw = cfg.value_json or {}
        cols = raw.get("collections") or {}
        if not isinstance(cols, dict):
            cols = {}

        col = cols.get(id)
        if not isinstance(col, dict):
            col = {"id": id, "name": "", "schema": {}, "items": [], "published": False}

        if body.name is not None:
            col["name"] = body.name.strip()
        if body.schema_ is not None:
            col["schema"] = body.schema_ if isinstance(body.schema_, dict) else {}
        if body.items is not None:
            col["items"] = body.items if isinstance(body.items, list) else []

        col["updatedAt"] = _iso(datetime.utcnow())
        cols[id] = col
        raw["collections"] = cols
        _ensure_json_serializable(raw, field_name="collections")
        _set_value_json(cfg, raw)
        await session.commit()

    return ok(data=col, request_id=request.state.request_id)


@router.post("/admin/mini-program/collections/{id}/publish")
async def admin_publish_collection(request: Request, id: str, _admin: ActorContext = Depends(require_admin_phone_bound)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_COLLECTIONS)
        raw = cfg.value_json or {}
        cols = raw.get("collections") or {}
        if not isinstance(cols, dict):
            cols = {}
        col = cols.get(id)
        if not isinstance(col, dict):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "集合不存在"})

        if bool(col.get("published")) is True:
            return ok(
                data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
                request_id=request.state.request_id,
            )

        v = _now_version()
        col["published"] = True
        col["version"] = v
        col["updatedAt"] = _iso(datetime.utcnow())
        cols[id] = col
        raw["collections"] = cols
        raw["version"] = v
        _ensure_json_serializable(raw, field_name="collections")
        _set_value_json(cfg, raw)
        session.add(
            _audit_mini_program_config(
                request=request,
                admin_id=str(_admin.sub),
                action=AuditAction.PUBLISH.value,
                resource_id=f"COLLECTIONS:{id}",
                meta={"key": _KEY_COLLECTIONS, "collectionId": id, "afterPublished": True},
            )
        )
        await session.commit()

    return ok(
        data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )


@router.post("/admin/mini-program/collections/{id}/offline")
async def admin_offline_collection(request: Request, id: str, _admin: ActorContext = Depends(require_admin_phone_bound)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_COLLECTIONS)
        raw = cfg.value_json or {}
        cols = raw.get("collections") or {}
        if not isinstance(cols, dict):
            cols = {}
        col = cols.get(id)
        if not isinstance(col, dict):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "集合不存在"})

        if bool(col.get("published")) is False:
            return ok(
                data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
                request_id=request.state.request_id,
            )

        v = _now_version()
        col["published"] = False
        col["version"] = v
        col["updatedAt"] = _iso(datetime.utcnow())
        cols[id] = col
        raw["collections"] = cols
        raw["version"] = v
        _ensure_json_serializable(raw, field_name="collections")
        _set_value_json(cfg, raw)
        session.add(
            _audit_mini_program_config(
                request=request,
                admin_id=str(_admin.sub),
                action=AuditAction.OFFLINE.value,
                resource_id=f"COLLECTIONS:{id}",
                meta={"key": _KEY_COLLECTIONS, "collectionId": id, "afterPublished": False},
            )
        )
        await session.commit()

    return ok(
        data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )
