"""Admin 区域/城市配置（REGION_CITIES）。

目标：
- 补齐 REGION_CITIES 的维护与发布闭环，让 H5/官网/小程序/Provider 可复用同一读侧。

存储承载：
- SystemConfig.key = REGION_CITIES
- value_json:
  - items: [{code,name,sort,enabled,published}]
  - version: string（publish/offline 时写入）

一键导入：
- 使用 gb2260 生成“省级 + 地级（含自治州/地区）”列表（不含区县）
"""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType, CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["admin-regions"])

_KEY_REGION_CITIES = "REGION_CITIES"


def _ensure_json_serializable(value: Any, *, field_name: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 不是合法 JSON"}) from exc


def _now_version() -> str:
    return str(int(time.time()))


def _audit_region_cities(
    *,
    request: Request,
    admin_id: str,
    action: str,
    meta: dict[str, Any] | None = None,
) -> AuditLog:
    return AuditLog(
        id=str(uuid4()),
        actor_type=AuditActorType.ADMIN.value,
        actor_id=admin_id,
        action=action,
        resource_type="REGION_CITIES",
        resource_id="REGION_CITIES",
        summary=f"ADMIN 更新城市配置：{action}",
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
        description=f"Auto-created by admin regions config for {key}",
        status=CommonEnabledStatus.ENABLED.value,
    )
    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)
    return cfg


class AdminRegionItem(BaseModel):
    code: str = Field(..., min_length=3)
    name: str = Field(..., min_length=1)
    sort: int = 0
    enabled: bool = True
    # 注意：published 由 publish/offline 控制；PUT 会忽略该字段
    published: bool | None = None

    @model_validator(mode="after")
    def _validate(self):
        self.code = str(self.code or "").strip()
        self.name = str(self.name or "").strip()
        if not self.code or ":" not in self.code:
            raise ValueError("code 必须形如 PROVINCE:110000 或 CITY:110100")
        prefix, raw = self.code.split(":", 1)
        prefix = prefix.upper().strip()
        raw = raw.strip()
        if prefix not in {"PROVINCE", "CITY"}:
            raise ValueError("code 前缀仅支持 PROVINCE/CITY")
        if not (raw.isdigit() and len(raw) == 6):
            raise ValueError("code 冒号后的部分必须为 6 位数字行政区划码")
        self.code = f"{prefix}:{raw}"
        if not self.name:
            raise ValueError("name 不能为空")
        return self


class AdminPutRegionCitiesBody(BaseModel):
    items: list[AdminRegionItem]
    version: str | None = None


@router.get("/admin/regions/cities")
async def admin_get_region_cities(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_REGION_CITIES).limit(1))).first()
    if cfg is None:
        return ok(data={"items": [], "version": "0"}, request_id=request.state.request_id)

    raw = cfg.value_json or {}
    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []
    version = str(raw.get("version") or "0")
    return ok(data={"items": items, "version": version}, request_id=request.state.request_id)


@router.put("/admin/regions/cities")
async def admin_put_region_cities(request: Request, body: AdminPutRegionCitiesBody, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_REGION_CITIES)
        # 重要：避免对 JSON 字段原地修改导致 ORM 无法识别变更（发布/保存“看起来没生效”）
        raw = dict(cfg.value_json or {})
        existing_items = raw.get("items") or []
        if not isinstance(existing_items, list):
            existing_items = []

        published_by_code: dict[str, bool] = {}
        for x in existing_items:
            if isinstance(x, dict) and x.get("code"):
                published_by_code[str(x.get("code"))] = bool(x.get("published"))

        new_items: list[dict] = []
        for x in body.items:
            d = x.model_dump()
            code = str(d.get("code") or "")
            d["published"] = bool(published_by_code.get(code, False))
            new_items.append(d)

        raw["items"] = new_items
        if body.version is not None:
            raw.setdefault("draftVersion", str(body.version))

        _ensure_json_serializable(raw, field_name="REGION_CITIES")
        cfg.value_json = raw
        flag_modified(cfg, "value_json")
        await session.commit()

    return ok(
        data={"items": new_items, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )


@router.post("/admin/regions/cities/publish")
async def admin_publish_region_cities(request: Request, _admin: ActorContext = Depends(require_admin_phone_bound)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_REGION_CITIES)
        raw = dict(cfg.value_json or {})
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
        _ensure_json_serializable(raw, field_name="REGION_CITIES")
        cfg.value_json = raw
        flag_modified(cfg, "value_json")
        session.add(
            _audit_region_cities(
                request=request,
                admin_id=str(_admin.sub),
                action=AuditAction.PUBLISH.value,
                meta={"afterPublished": True, "itemCount": len(items), "version": str(raw.get("version") or "0")},
            )
        )
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)


@router.post("/admin/regions/cities/offline")
async def admin_offline_region_cities(request: Request, _admin: ActorContext = Depends(require_admin_phone_bound)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_REGION_CITIES)
        raw = dict(cfg.value_json or {})
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
        _ensure_json_serializable(raw, field_name="REGION_CITIES")
        cfg.value_json = raw
        flag_modified(cfg, "value_json")
        session.add(
            _audit_region_cities(
                request=request,
                admin_id=str(_admin.sub),
                action=AuditAction.OFFLINE.value,
                meta={"afterPublished": False, "itemCount": len(items), "version": str(raw.get("version") or "0")},
            )
        )
        await session.commit()

    return ok(data={"success": True, "version": str((cfg.value_json or {}).get("version") or "0")}, request_id=request.state.request_id)


def _normalize_name_for_city(*, code6: str, name: str, province_name: str) -> str:
    """修正直辖市/异常占位名的展示口径。

    gb2260 对 110100/120100/310100/500100 等 city-level 可能返回“市辖区”，
    端侧希望展示为“北京/天津/上海/重庆”。
    """

    n = str(name or "").strip()
    if n in {"市辖区", "县"}:
        prov = str(province_name or "").strip()
        # 省级名称通常为“北京市/天津市/上海市/重庆市”
        for suf in ("市", "省", "自治区", "特别行政区"):
            if prov.endswith(suf):
                prov = prov[: -len(suf)]
                break
        return prov or n
    if "省直辖" in n or "自治区直辖" in n:
        return ""
    return n


def _build_cn_province_city_items() -> list[dict]:
    """生成全国省/市（地级）列表，不含区县。"""

    try:
        import gb2260  # type: ignore
        import gb2260.data as gbdata  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail={"code": "INTERNAL_ERROR", "message": "gb2260 未正确安装，无法导入全国省市数据"}
        ) from exc

    cur = gbdata.data.get(None) or {}
    codes = []
    for k in cur.keys():
        try:
            codes.append(int(k))
        except Exception:
            continue
    codes = sorted(set(codes))

    provinces: list[tuple[str, str]] = []
    cities: list[tuple[str, str]] = []

    for code in codes:
        code6 = f"{code:06d}"
        if code % 10000 == 0:
            d = gb2260.get(code6)
            name = str(getattr(d, "name", "") or "").strip()
            if not name:
                continue
            provinces.append((code6, name))
        elif code % 100 == 0:
            d = gb2260.get(code6)
            name = str(getattr(d, "name", "") or "").strip()
            prov = getattr(d, "province", None)
            prov_name = str(getattr(prov, "name", "") or "").strip() if prov is not None else ""
            fixed = _normalize_name_for_city(code6=code6, name=name, province_name=prov_name)
            if not fixed:
                continue
            cities.append((code6, fixed))

    # 直辖市：只保留一个“城市级”入口（否则会出现“市辖区/县”等占位）
    municipality_prov = {"110000", "120000", "310000", "500000"}
    municipality_city_keep = {"110100", "120100", "310100", "500100"}
    cities = [(c, n) for (c, n) in cities if (c in municipality_city_keep) or (c[:2] + "0000" not in municipality_prov)]

    items: list[dict] = []
    sort = 0
    for code6, name in provinces:
        sort += 1
        items.append(
            {
                "code": f"PROVINCE:{code6}",
                "name": name,
                "sort": sort,
                "enabled": True,
                "published": False,
            }
        )

    for code6, name in cities:
        sort += 1
        items.append(
            {
                "code": f"CITY:{code6}",
                "name": name,
                "sort": sort,
                "enabled": True,
                "published": False,
            }
        )

    return items


@router.post("/admin/regions/cities/import-cn")
async def admin_import_cn_region_cities(
    request: Request, _admin: ActorContext = Depends(require_admin_phone_bound), replace: bool = True
):
    """一键导入全国省/市列表（草稿），默认覆盖当前 items。"""

    items = _build_cn_province_city_items()
    if not items:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "导入失败：未生成任何省市数据"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_config(session, _KEY_REGION_CITIES)
        raw = dict(cfg.value_json or {})
        existing = raw.get("items") or []
        if not isinstance(existing, list):
            existing = []

        published_by_code: dict[str, bool] = {}
        for x in existing:
            if isinstance(x, dict) and x.get("code"):
                published_by_code[str(x.get("code"))] = bool(x.get("published"))

        # 导入属于“草稿写入”：保留每条 code 的已发布状态回显（与 PUT 行为一致）
        new_items: list[dict] = []
        for x in items:
            if not isinstance(x, dict):
                continue
            code = str(x.get("code") or "")
            x2 = dict(x)
            x2["published"] = bool(published_by_code.get(code, False))
            new_items.append(x2)
        items = new_items

        if not replace:
            existing_by_code = {str(x.get("code")): x for x in existing if isinstance(x, dict) and x.get("code")}
            for x in items:
                existing_by_code[str(x.get("code"))] = x
            items = list(existing_by_code.values())

        # replace=true 且导入结果与当前草稿一致：no-op（不写审计/不更新）
        if replace and existing == items:
            return ok(
                data={"success": True, "items": items, "version": str((cfg.value_json or {}).get("version") or "0")},
                request_id=request.state.request_id,
            )

        raw["items"] = items
        raw.setdefault("version", str(raw.get("version") or "0"))
        _ensure_json_serializable(raw, field_name="REGION_CITIES")
        cfg.value_json = raw
        flag_modified(cfg, "value_json")
        session.add(
            _audit_region_cities(
                request=request,
                admin_id=str(_admin.sub),
                action=AuditAction.UPDATE.value,
                meta={
                    "op": "import-cn",
                    "replace": bool(replace),
                    "itemCount": len(items),
                },
            )
        )
        await session.commit()

    return ok(
        data={"success": True, "items": items, "version": str((cfg.value_json or {}).get("version") or "0")},
        request_id=request.state.request_id,
    )


