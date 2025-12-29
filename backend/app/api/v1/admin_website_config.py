"""Admin Website 配置（v1 最小可执行）。

目标：
- 让官网“导流外链”可由管理系统在运行时修改（无需重建前端）。
- 让官网“页脚与联系方式”“首页推荐场所”可由管理系统在运行时修改（无需重建前端）。

规格来源：
- specs/health-services-platform/design.md -> Website 导流外链（WEBSITE_EXTERNAL_LINKS）
- specs/功能实现/website/api-contracts.md
- specs/功能实现/website/admin-backoffice.md
"""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType, CommonEnabledStatus, VenuePublishStatus
from app.models.system_config import SystemConfig
from app.models.venue import Venue
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["admin-website-config"])

_KEY_EXTERNAL_LINKS = "WEBSITE_EXTERNAL_LINKS"
_KEY_FOOTER_CONFIG = "WEBSITE_FOOTER_CONFIG"
_KEY_RECOMMENDED_VENUES = "WEBSITE_HOME_RECOMMENDED_VENUES"
_KEY_SITE_SEO = "WEBSITE_SITE_SEO"
_KEY_NAV_CONTROL = "WEBSITE_NAV_CONTROL"
_KEY_MAINTENANCE_MODE = "WEBSITE_MAINTENANCE_MODE"


def _ensure_json_serializable(value: Any, *, field_name: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 不是合法 JSON"}) from exc


def _now_version() -> str:
    return str(int(time.time()))


def _strip_version(x: dict | None) -> dict:
    if not isinstance(x, dict):
        return {}
    y = dict(x)
    y.pop("version", None)
    return y


def _read_version(x: dict | None) -> str:
    if not isinstance(x, dict):
        return "0"
    return str(x.get("version") or "0")


def _audit_website_config_change(
    *,
    request: Request,
    admin_id: str,
    key: str,
    before_version: str,
    after_version: str,
    changed_fields: list[str] | None = None,
) -> AuditLog:
    return AuditLog(
        id=str(uuid4()),
        actor_type=AuditActorType.ADMIN.value,
        actor_id=admin_id,
        action=AuditAction.UPDATE.value,
        resource_type="WEBSITE_CONFIG",
        resource_id=key,
        summary=f"ADMIN 更新官网配置：{key}",
        ip=getattr(getattr(request, "client", None), "host", None),
        user_agent=request.headers.get("User-Agent"),
        metadata_json={
            "path": request.url.path,
            "method": request.method,
            "requestId": request.state.request_id,
            "key": key,
            "beforeVersion": before_version,
            "afterVersion": after_version,
            "changedFields": changed_fields or None,
        },
    )


class SiteSeoConfig(BaseModel):
    siteName: str = Field(..., min_length=1)
    defaultTitle: str = Field(..., min_length=1)
    defaultDescription: str = Field(..., min_length=1)
    canonicalBaseUrl: str | None = None
    robots: str | None = None
    version: str | None = None

    @model_validator(mode="after")
    def _validate(self):
        self.siteName = str(self.siteName or "").strip()
        self.defaultTitle = str(self.defaultTitle or "").strip()
        self.defaultDescription = str(self.defaultDescription or "").strip()
        self.canonicalBaseUrl = str(self.canonicalBaseUrl or "").strip()
        self.robots = str(self.robots or "").strip()

        if not self.siteName:
            raise ValueError("siteName 不能为空")
        if not self.defaultTitle:
            raise ValueError("defaultTitle 不能为空")
        if not self.defaultDescription:
            raise ValueError("defaultDescription 不能为空")
        if self.canonicalBaseUrl and not (
            self.canonicalBaseUrl.startswith("http://") or self.canonicalBaseUrl.startswith("https://")
        ):
            raise ValueError("canonicalBaseUrl 必须是 http(s):// URL（或留空）")
        return self


@router.get("/admin/website/site-seo")
async def admin_get_website_site_seo(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_SITE_SEO).limit(1))).first()
    if cfg is None:
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
    return ok(data=cfg.value_json or {}, request_id=request.state.request_id)


@router.put("/admin/website/site-seo")
async def admin_put_website_site_seo(request: Request, body: SiteSeoConfig, _admin: ActorContext = Depends(require_admin_phone_bound)):
    _ensure_json_serializable(body.model_dump(), field_name="body")
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_SITE_SEO).limit(1))).first()
        before_value = cfg.value_json if cfg else None
        before_version = _read_version(before_value if isinstance(before_value, dict) else None)
        if cfg is None:
            cfg = SystemConfig(
                id=str(uuid4()),
                key=_KEY_SITE_SEO,
                value_json={},
                description="Managed by admin website config",
                status=CommonEnabledStatus.ENABLED.value,
            )
            session.add(cfg)

        value = body.model_dump()
        value["canonicalBaseUrl"] = str(value.get("canonicalBaseUrl") or "").strip()
        value["robots"] = str(value.get("robots") or "index,follow").strip()
        value["version"] = _now_version()

        # no-op：仅 version 不同不算变更；不刷审计、不更新
        if cfg.value_json and _strip_version(cfg.value_json) == _strip_version(value):
            return ok(data=cfg.value_json, request_id=request.state.request_id)

        cfg.value_json = value
        cfg.status = CommonEnabledStatus.ENABLED.value
        cfg.description = "Managed by admin website config"
        session.add(
            _audit_website_config_change(
                request=request,
                admin_id=admin_id,
                key=_KEY_SITE_SEO,
                before_version=before_version,
                after_version=str(value.get("version") or "0"),
                changed_fields=sorted(list(_strip_version(value).keys())),
            )
        )
        await session.commit()

    return ok(data=value, request_id=request.state.request_id)


class NavItemSwitch(BaseModel):
    enabled: bool = True


class NavControlConfig(BaseModel):
    navItems: dict[str, NavItemSwitch] = Field(default_factory=dict)
    version: str | None = None

    @model_validator(mode="after")
    def _validate(self):
        required = {"home", "business", "venues", "content", "about", "contact"}
        keys = set(self.navItems.keys())
        missing = required - keys
        if missing:
            raise ValueError(f"navItems 缺少项：{sorted(list(missing))}")
        extra = keys - required
        if extra:
            raise ValueError(f"navItems 包含不支持的项：{sorted(list(extra))}")
        return self


@router.get("/admin/website/nav-control")
async def admin_get_website_nav_control(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_NAV_CONTROL).limit(1))).first()
    if cfg is None:
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
    return ok(data=cfg.value_json or {}, request_id=request.state.request_id)


@router.put("/admin/website/nav-control")
async def admin_put_website_nav_control(request: Request, body: NavControlConfig, _admin: ActorContext = Depends(require_admin_phone_bound)):
    _ensure_json_serializable(body.model_dump(), field_name="body")
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_NAV_CONTROL).limit(1))).first()
        before_version = _read_version(cfg.value_json if cfg and isinstance(cfg.value_json, dict) else None)
        if cfg is None:
            cfg = SystemConfig(
                id=str(uuid4()),
                key=_KEY_NAV_CONTROL,
                value_json={},
                description="Managed by admin website config",
                status=CommonEnabledStatus.ENABLED.value,
            )
            session.add(cfg)
        value = body.model_dump()
        value["version"] = _now_version()

        if cfg.value_json and _strip_version(cfg.value_json) == _strip_version(value):
            return ok(data=cfg.value_json, request_id=request.state.request_id)

        cfg.value_json = value
        cfg.status = CommonEnabledStatus.ENABLED.value
        cfg.description = "Managed by admin website config"
        session.add(
            _audit_website_config_change(
                request=request,
                admin_id=admin_id,
                key=_KEY_NAV_CONTROL,
                before_version=before_version,
                after_version=str(value.get("version") or "0"),
                changed_fields=["navItems"],
            )
        )
        await session.commit()
    return ok(data=value, request_id=request.state.request_id)


class MaintenanceModeConfig(BaseModel):
    enabled: bool = False
    messageTitle: str = Field(..., min_length=1)
    messageBody: str = Field(..., min_length=1)
    allowPaths: list[str] = Field(default_factory=list)
    allowIps: list[str] = Field(default_factory=list)
    version: str | None = None

    @model_validator(mode="after")
    def _validate(self):
        self.messageTitle = str(self.messageTitle or "").strip()
        self.messageBody = str(self.messageBody or "").strip()
        self.allowPaths = [str(x).strip() for x in (self.allowPaths or []) if str(x).strip()]
        self.allowIps = [str(x).strip() for x in (self.allowIps or []) if str(x).strip()]
        for p in self.allowPaths:
            if not p.startswith("/"):
                raise ValueError("allowPaths 里的每一项必须以 / 开头")
        return self


@router.get("/admin/website/maintenance-mode")
async def admin_get_website_maintenance_mode(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_MAINTENANCE_MODE).limit(1))
        ).first()
    if cfg is None:
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
    return ok(data=cfg.value_json or {}, request_id=request.state.request_id)


@router.put("/admin/website/maintenance-mode")
async def admin_put_website_maintenance_mode(
    request: Request, body: MaintenanceModeConfig, _admin: ActorContext = Depends(require_admin_phone_bound)
):
    _ensure_json_serializable(body.model_dump(), field_name="body")
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_MAINTENANCE_MODE).limit(1))
        ).first()
        before_version = _read_version(cfg.value_json if cfg and isinstance(cfg.value_json, dict) else None)
        if cfg is None:
            cfg = SystemConfig(
                id=str(uuid4()),
                key=_KEY_MAINTENANCE_MODE,
                value_json={},
                description="Managed by admin website config",
                status=CommonEnabledStatus.ENABLED.value,
            )
            session.add(cfg)
        value = body.model_dump()
        value["version"] = _now_version()

        if cfg.value_json and _strip_version(cfg.value_json) == _strip_version(value):
            return ok(data=cfg.value_json, request_id=request.state.request_id)

        cfg.value_json = value
        cfg.status = CommonEnabledStatus.ENABLED.value
        cfg.description = "Managed by admin website config"
        session.add(
            _audit_website_config_change(
                request=request,
                admin_id=admin_id,
                key=_KEY_MAINTENANCE_MODE,
                before_version=before_version,
                after_version=str(value.get("version") or "0"),
                changed_fields=["enabled", "messageTitle", "messageBody", "allowPaths", "allowIps"],
            )
        )
        await session.commit()
    return ok(data=value, request_id=request.state.request_id)


class PutWebsiteExternalLinksBody(BaseModel):
    miniProgramUrl: str = Field(..., min_length=1)
    h5BuyUrl: str = Field(..., min_length=1)
    version: str | None = None

    @model_validator(mode="after")
    def _validate_urls(self):
        for k in ("miniProgramUrl", "h5BuyUrl"):
            url = str(getattr(self, k) or "").strip()
            if not (url.startswith("http://") or url.startswith("https://")):
                raise ValueError(f"{k} 必须是 http(s):// URL")
            setattr(self, k, url)
        return self


@router.get("/admin/website/external-links")
async def admin_get_website_external_links(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_EXTERNAL_LINKS).limit(1))
        ).first()
    if cfg is None:
        return ok(data={"miniProgramUrl": "", "h5BuyUrl": "", "version": "0"}, request_id=request.state.request_id)
    return ok(data=cfg.value_json or {}, request_id=request.state.request_id)


@router.put("/admin/website/external-links")
async def admin_put_website_external_links(
    request: Request, body: PutWebsiteExternalLinksBody, _admin: ActorContext = Depends(require_admin_phone_bound)
):
    _ensure_json_serializable(body.model_dump(), field_name="body")
    admin_id = str(_admin.sub)

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_EXTERNAL_LINKS).limit(1))
        ).first()
        before_version = _read_version(cfg.value_json if cfg and isinstance(cfg.value_json, dict) else None)
        if cfg is None:
            cfg = SystemConfig(
                id=str(uuid4()),
                key=_KEY_EXTERNAL_LINKS,
                value_json={},
                description="Managed by admin website config",
                status=CommonEnabledStatus.ENABLED.value,
            )
            session.add(cfg)

        value = body.model_dump()
        value["version"] = _now_version()

        if cfg.value_json and _strip_version(cfg.value_json) == _strip_version(value):
            return ok(data=cfg.value_json, request_id=request.state.request_id)

        cfg.value_json = value
        cfg.status = CommonEnabledStatus.ENABLED.value
        cfg.description = "Managed by admin website config"
        session.add(
            _audit_website_config_change(
                request=request,
                admin_id=admin_id,
                key=_KEY_EXTERNAL_LINKS,
                before_version=before_version,
                after_version=str(value.get("version") or "0"),
                changed_fields=["miniProgramUrl", "h5BuyUrl"],
            )
        )
        await session.commit()

    return ok(data=value, request_id=request.state.request_id)


class FooterConfig(BaseModel):
    companyName: str = Field(..., min_length=1)
    cooperationEmail: str = Field(..., min_length=1)
    cooperationPhone: str = Field(..., min_length=1)
    icpBeianNo: str | None = None
    icpBeianLink: str | None = None
    publicAccountQrUrl: str | None = None
    miniProgramQrUrl: str | None = None
    version: str | None = None


@router.get("/admin/website/footer-config")
async def admin_get_website_footer_config(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_FOOTER_CONFIG).limit(1))).first()
    if cfg is None:
        return ok(
            data={
                "companyName": "",
                "cooperationEmail": "",
                "cooperationPhone": "",
                "icpBeianNo": "",
                "icpBeianLink": "",
                "publicAccountQrUrl": "",
                "miniProgramQrUrl": "",
                "version": "0",
            },
            request_id=request.state.request_id,
        )
    return ok(data=cfg.value_json or {}, request_id=request.state.request_id)


@router.put("/admin/website/footer-config")
async def admin_put_website_footer_config(
    request: Request, body: FooterConfig, _admin: ActorContext = Depends(require_admin_phone_bound)
):
    _ensure_json_serializable(body.model_dump(), field_name="body")
    admin_id = str(_admin.sub)

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_FOOTER_CONFIG).limit(1))).first()
        before_version = _read_version(cfg.value_json if cfg and isinstance(cfg.value_json, dict) else None)
        if cfg is None:
            cfg = SystemConfig(
                id=str(uuid4()),
                key=_KEY_FOOTER_CONFIG,
                value_json={},
                description="Managed by admin website config",
                status=CommonEnabledStatus.ENABLED.value,
            )
            session.add(cfg)

        value = body.model_dump()
        value["companyName"] = str(value.get("companyName") or "").strip()
        value["cooperationEmail"] = str(value.get("cooperationEmail") or "").strip()
        value["cooperationPhone"] = str(value.get("cooperationPhone") or "").strip()
        value["icpBeianNo"] = (str(value.get("icpBeianNo") or "").strip()) or ""
        value["icpBeianLink"] = (str(value.get("icpBeianLink") or "").strip()) or ""
        value["publicAccountQrUrl"] = (str(value.get("publicAccountQrUrl") or "").strip()) or ""
        value["miniProgramQrUrl"] = (str(value.get("miniProgramQrUrl") or "").strip()) or ""

        value["version"] = _now_version()

        if cfg.value_json and _strip_version(cfg.value_json) == _strip_version(value):
            return ok(data=cfg.value_json, request_id=request.state.request_id)

        cfg.value_json = value
        cfg.status = CommonEnabledStatus.ENABLED.value
        cfg.description = "Managed by admin website config"
        session.add(
            _audit_website_config_change(
                request=request,
                admin_id=admin_id,
                key=_KEY_FOOTER_CONFIG,
                before_version=before_version,
                after_version=str(value.get("version") or "0"),
                changed_fields=[
                    "companyName",
                    "cooperationEmail",
                    "cooperationPhone",
                    "icpBeianNo",
                    "icpBeianLink",
                    "publicAccountQrUrl",
                    "miniProgramQrUrl",
                ],
            )
        )
        await session.commit()

    return ok(data=value, request_id=request.state.request_id)


class RecommendedVenueItem(BaseModel):
    venueId: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _trim(self):
        self.venueId = str(self.venueId or "").strip()
        if not self.venueId:
            raise ValueError("venueId 不能为空")
        return self


class PutRecommendedVenuesBody(BaseModel):
    items: list[RecommendedVenueItem] = Field(default_factory=list)
    version: str | None = None
    enabled: bool | None = None


@router.get("/admin/website/home/recommended-venues")
async def admin_get_website_home_recommended_venues(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_RECOMMENDED_VENUES).limit(1))
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

        venues = (
            (await session.scalars(select(Venue).where(Venue.id.in_(venue_ids)))).all() if venue_ids else []
        )
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

    return ok(data={"items": out_items, "version": version, "enabled": enabled}, request_id=request.state.request_id)


@router.put("/admin/website/home/recommended-venues")
async def admin_put_website_home_recommended_venues(
    request: Request, body: PutRecommendedVenuesBody, _admin: ActorContext = Depends(require_admin_phone_bound)
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

        cfg = (
            await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_RECOMMENDED_VENUES).limit(1))
        ).first()
        before_version = _read_version(cfg.value_json if cfg and isinstance(cfg.value_json, dict) else None)
        if cfg is None:
            cfg = SystemConfig(
                id=str(uuid4()),
                key=_KEY_RECOMMENDED_VENUES,
                value_json={},
                description="Managed by admin website config",
                status=CommonEnabledStatus.ENABLED.value,
            )
            session.add(cfg)

        value = {"version": _now_version(), "items": [{"venueId": x} for x in venue_ids]}

        target_status = CommonEnabledStatus.ENABLED.value if (body.enabled is not False) else CommonEnabledStatus.DISABLED.value
        same_value = bool(cfg.value_json) and _strip_version(cfg.value_json) == _strip_version(value)
        same_status = str(cfg.status or "") == str(target_status)
        if same_value and same_status:
            out = cfg.value_json or {}
            out["enabled"] = (cfg.status == CommonEnabledStatus.ENABLED.value)
            return ok(data=out, request_id=request.state.request_id)

        cfg.value_json = value
        cfg.status = target_status
        cfg.description = "Managed by admin website config"
        changed_fields = ["items"]
        if not same_status:
            changed_fields.append("status")
        session.add(
            _audit_website_config_change(
                request=request,
                admin_id=admin_id,
                key=_KEY_RECOMMENDED_VENUES,
                before_version=before_version,
                after_version=str(value.get("version") or "0"),
                changed_fields=changed_fields,
            )
        )
        await session.commit()

    value["enabled"] = (target_status == CommonEnabledStatus.ENABLED.value)
    return ok(data=value, request_id=request.state.request_id)


