"""Admin 服务包阶梯价格配置（v1.1 最小可执行）。

规格来源：
- specs/health-services-platform/prototypes/admin.md -> 健行天下：区域/等级/阶梯价格配置
- specs/功能实现/admin/tasks.md -> T-H02

存储承载（实现细节）：
- SystemConfig.key：SERVICE_PACKAGE_PRICING

发布口径（v1.1）：
- PUT 仅更新草稿（保留已存在 published 状态）
- publish/offline 将所有规则的 published 置为 True/False 并 bump version
"""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.api.v1.deps import require_admin
from app.models.enums import CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["admin-service-package-pricing"])

_KEY = "SERVICE_PACKAGE_PRICING"


def _ensure_json_serializable(value: Any, *, field_name: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 不是合法 JSON"}
        ) from exc


def _now_version() -> str:
    return str(int(time.time()))


async def _get_or_create_config(session) -> SystemConfig:
    cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY).limit(1))).first()
    if cfg is not None:
        return cfg
    cfg = SystemConfig(
        id=str(uuid4()),
        key=_KEY,
        value_json={},
        description="Auto-created by admin service package pricing",
        status=CommonEnabledStatus.ENABLED.value,
    )
    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)
    return cfg


class PriceObj(BaseModel):
    original: float = Field(..., ge=0)
    employee: float | None = Field(default=None, ge=0)
    member: float | None = Field(default=None, ge=0)
    activity: float | None = Field(default=None, ge=0)


class PricingRuleItem(BaseModel):
    id: str = Field(..., min_length=1)
    templateId: str = Field(..., min_length=1)
    regionScope: str = Field(..., min_length=1)
    tier: str = Field(..., min_length=1)
    price: PriceObj
    enabled: bool = True
    published: bool | None = None  # 仅用于回显；PUT 时会被忽略并保留旧值

    @model_validator(mode="after")
    def _normalize(self):
        self.id = str(self.id).strip()
        self.templateId = str(self.templateId).strip()
        self.regionScope = str(self.regionScope).strip()
        self.tier = str(self.tier).strip()
        if not self.id:
            raise ValueError("id 不能为空")
        return self


class PutPricingBody(BaseModel):
    items: list[PricingRuleItem] = Field(default_factory=list)
    version: str | None = None

    @model_validator(mode="after")
    def _validate_unique_key(self):
        # 最小约束：同一 (templateId, regionScope, tier) 组合只能出现 1 次（避免裁决歧义）
        seen: set[tuple[str, str, str]] = set()
        for x in self.items:
            k = (str(x.templateId), str(x.regionScope), str(x.tier))
            if k in seen:
                raise ValueError(f"重复规则：templateId/regionScope/tier={k[0]}/{k[1]}/{k[2]}")
            seen.add(k)
        return self


@router.get("/admin/service-package-pricing")
async def admin_get_pricing(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY).limit(1))).first()
    if cfg is None:
        return ok(data={"items": [], "version": "0"}, request_id=request.state.request_id)
    raw = cfg.value_json or {}
    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []
    version = str(raw.get("version") or "0")
    return ok(data={"items": items, "version": version}, request_id=request.state.request_id)


@router.put("/admin/service-package-pricing")
async def admin_put_pricing(request: Request, body: PutPricingBody, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session)
        raw = cfg.value_json or {}
        existing_items = raw.get("items") or []
        if not isinstance(existing_items, list):
            existing_items = []

        published_by_id: dict[str, bool] = {}
        for x in existing_items:
            if isinstance(x, dict) and x.get("id"):
                published_by_id[str(x.get("id"))] = bool(x.get("published"))

        new_items: list[dict] = []
        for x in body.items:
            d = x.model_dump()
            item_id = str(d.get("id") or "")
            d["published"] = bool(published_by_id.get(item_id, False))

            # v1 运营口径（健行天下服务包）：仅使用“原价”作为最终计价字段；
            # employee/member/activity 保留为结构兼容字段，但在服务包定价中不开放配置，避免误导。
            if isinstance(d.get("price"), dict):
                d["price"]["employee"] = None
                d["price"]["member"] = None
                d["price"]["activity"] = None
            new_items.append(d)

        raw["items"] = new_items
        if body.version is not None:
            raw.setdefault("draftVersion", str(body.version))

        _ensure_json_serializable(raw, field_name="servicePackagePricing")
        cfg.value_json = raw
        await session.commit()

    return ok(
        data={"items": new_items, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )


@router.post("/admin/service-package-pricing/publish")
async def admin_publish_pricing(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session)
        raw = cfg.value_json or {}
        items = raw.get("items") or []
        if not isinstance(items, list):
            items = []

        for x in items:
            if isinstance(x, dict):
                x["published"] = True
        raw["items"] = items
        raw["version"] = _now_version()
        _ensure_json_serializable(raw, field_name="servicePackagePricing")
        cfg.value_json = raw
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)


@router.post("/admin/service-package-pricing/offline")
async def admin_offline_pricing(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session)
        raw = cfg.value_json or {}
        items = raw.get("items") or []
        if not isinstance(items, list):
            items = []

        for x in items:
            if isinstance(x, dict):
                x["published"] = False
        raw["items"] = items
        raw["version"] = _now_version()
        _ensure_json_serializable(raw, field_name="servicePackagePricing")
        cfg.value_json = raw
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)

