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

import time
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.enums import CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["admin-mini-program-config"])

_KEY_ENTRIES = "MINI_PROGRAM_ENTRIES"
_KEY_PAGES = "MINI_PROGRAM_PAGES"
_KEY_COLLECTIONS = "MINI_PROGRAM_COLLECTIONS"


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return parts[1].strip()


async def _require_admin(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_admin_token(token=token)
    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return payload


def _now_version() -> str:
    # v1：最小可用版本号（字符串），用于读侧缓存/比对
    return str(int(time.time()))


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone().isoformat()


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


# -----------------------------
# entries
# -----------------------------


class AdminEntryItem(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    iconUrl: str | None = None
    position: Literal["SHORTCUT", "OPERATION"]
    jumpType: Literal["AGG_PAGE", "INFO_PAGE", "WEBVIEW", "ROUTE"]
    targetId: str = Field(..., min_length=1)
    sort: int = 0
    enabled: bool = True
    # 注意：published 由 publish/offline 控制；PUT 会忽略该字段
    published: bool | None = None


class AdminPutEntriesBody(BaseModel):
    items: list[AdminEntryItem]
    version: str | None = None


@router.get("/admin/mini-program/entries")
async def admin_get_entries(request: Request, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)
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
async def admin_put_entries(request: Request, body: AdminPutEntriesBody, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

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

        cfg.value_json = raw
        await session.commit()

    return ok(data={"items": new_items, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)


@router.post("/admin/mini-program/entries/publish")
async def admin_publish_entries(request: Request, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_ENTRIES)
        raw = cfg.value_json or {}
        items = raw.get("items") or []
        if not isinstance(items, list):
            items = []

        for x in items:
            if isinstance(x, dict):
                x["published"] = True
        raw["items"] = items
        raw["version"] = _now_version()
        cfg.value_json = raw
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)


@router.post("/admin/mini-program/entries/offline")
async def admin_offline_entries(request: Request, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_ENTRIES)
        raw = cfg.value_json or {}
        items = raw.get("items") or []
        if not isinstance(items, list):
            items = []

        for x in items:
            if isinstance(x, dict):
                x["published"] = False
        raw["items"] = items
        raw["version"] = _now_version()
        cfg.value_json = raw
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)


# -----------------------------
# pages
# -----------------------------


class AdminPageItem(BaseModel):
    id: str = Field(..., min_length=1)
    type: Literal["AGG_PAGE", "INFO_PAGE"]
    config: dict[str, Any] = Field(default_factory=dict)
    version: str | None = None
    published: bool = False


@router.get("/admin/mini-program/pages")
async def admin_get_pages(request: Request, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

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
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    # 规格：published 只能通过 publish/offline 控制
    if body.published is not None:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "published 不允许通过该接口修改"})

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
        if body.version is not None:
            page.setdefault("draftVersion", str(body.version))

        pages[id] = page
        raw["pages"] = pages
        cfg.value_json = raw
        await session.commit()

    return ok(
        data={
            "id": str(page.get("id") or id),
            "type": page.get("type"),
            "config": page.get("config") if isinstance(page.get("config"), dict) else {},
            "version": str(page.get("version") or raw.get("version") or "0"),
            "published": bool(page.get("published")),
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/mini-program/pages/{id}/publish")
async def admin_publish_page(request: Request, id: str, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

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

        v = _now_version()
        page["published"] = True
        page["version"] = v
        pages[id] = page
        raw["pages"] = pages
        raw["version"] = v
        cfg.value_json = raw
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)


@router.post("/admin/mini-program/pages/{id}/offline")
async def admin_offline_page(request: Request, id: str, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

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

        v = _now_version()
        page["published"] = False
        page["version"] = v
        pages[id] = page
        raw["pages"] = pages
        raw["version"] = v
        cfg.value_json = raw
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)


# -----------------------------
# collections
# -----------------------------


@router.get("/admin/mini-program/collections")
async def admin_get_collections(request: Request, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

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
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    # 规格：published 只能通过 publish/offline 控制
    if body.published is not None:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "published 不允许通过该接口修改"})

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
        cfg.value_json = raw
        await session.commit()

    return ok(data=col, request_id=request.state.request_id)


@router.post("/admin/mini-program/collections/{id}/publish")
async def admin_publish_collection(request: Request, id: str, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

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

        v = _now_version()
        col["published"] = True
        col["version"] = v
        col["updatedAt"] = _iso(datetime.utcnow())
        cols[id] = col
        raw["collections"] = cols
        raw["version"] = v
        cfg.value_json = raw
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)


@router.post("/admin/mini-program/collections/{id}/offline")
async def admin_offline_collection(request: Request, id: str, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

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

        v = _now_version()
        col["published"] = False
        col["version"] = v
        col["updatedAt"] = _iso(datetime.utcnow())
        cols[id] = col
        raw["collections"] = cols
        raw["version"] = v
        cfg.value_json = raw
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)

