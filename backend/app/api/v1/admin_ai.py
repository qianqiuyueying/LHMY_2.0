"""Admin AI 配置中心（阶段11，v1 最小可执行）。

规格来源（已确认）：
- specs/health-services-platform/design.md -> AI 对话能力（配置项/审计元数据）
- specs/health-services-platform/tasks.md -> 阶段11「规格补充（待确认）」-> 用户已确认

存储承载：
- SystemConfig.key = "AI_CONFIG"
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.enums import CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["admin-ai"])

_KEY_AI_CONFIG = "AI_CONFIG"


def _now_version() -> str:
    return str(int(time.time()))


def _mask_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    s = str(api_key).strip()
    if len(s) <= 8:
        return "****"
    return f"{s[:3]}****{s[-4:]}"


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


async def _get_or_create_ai_config(session) -> SystemConfig:
    cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_AI_CONFIG).limit(1))).first()
    if cfg is not None:
        return cfg

    default_value = {
        "enabled": False,
        "provider": "OPENAI_COMPAT",
        "baseUrl": "",
        "apiKey": "",
        "model": "",
        "systemPrompt": "",
        "temperature": 0.7,
        "maxTokens": 1024,
        "timeoutMs": 15000,
        "retries": 1,
        "rateLimitPerMinute": 30,
        "version": _now_version(),
    }
    cfg = SystemConfig(
        id=str(uuid4()),
        key=_KEY_AI_CONFIG,
        value_json=default_value,
        description="AI config for mini-program chat gateway",
        status=CommonEnabledStatus.ENABLED.value,
    )
    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)
    return cfg


def _parse_dt(raw: str, *, field_name: str) -> datetime:
    try:
        if len(raw) == 10:
            return datetime.fromisoformat(raw + "T00:00:00")
        return datetime.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}) from exc


def _normalize_value(value: dict) -> dict:
    v = dict(value or {})
    # 兜底：保证存在必要字段
    v.setdefault("enabled", False)
    v.setdefault("provider", "OPENAI_COMPAT")
    v.setdefault("baseUrl", "")
    v.setdefault("apiKey", "")
    v.setdefault("model", "")
    v.setdefault("systemPrompt", "")
    v.setdefault("temperature", 0.7)
    v.setdefault("maxTokens", 1024)
    v.setdefault("timeoutMs", 15000)
    v.setdefault("retries", 1)
    v.setdefault("rateLimitPerMinute", 30)
    v.setdefault("version", _now_version())
    return v


class AdminAiConfigResp(BaseModel):
    enabled: bool
    provider: Literal["OPENAI_COMPAT"]
    baseUrl: str
    model: str
    systemPrompt: str | None = None
    temperature: float | None = None
    maxTokens: int | None = None
    timeoutMs: int | None = None
    retries: int | None = None
    rateLimitPerMinute: int | None = None
    version: str
    apiKeyMasked: str | None = None


@router.get("/admin/ai/config")
async def admin_get_ai_config(
    request: Request,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_ai_config(session)
        v = _normalize_value(cfg.value_json)

    data = AdminAiConfigResp(
        enabled=bool(v.get("enabled", False)),
        provider="OPENAI_COMPAT",
        baseUrl=str(v.get("baseUrl", "") or ""),
        model=str(v.get("model", "") or ""),
        systemPrompt=(str(v.get("systemPrompt")) if v.get("systemPrompt") is not None else None),
        temperature=(float(v["temperature"]) if v.get("temperature") is not None else None),
        maxTokens=(int(v["maxTokens"]) if v.get("maxTokens") is not None else None),
        timeoutMs=(int(v["timeoutMs"]) if v.get("timeoutMs") is not None else None),
        retries=(int(v["retries"]) if v.get("retries") is not None else None),
        rateLimitPerMinute=(int(v["rateLimitPerMinute"]) if v.get("rateLimitPerMinute") is not None else None),
        version=str(v.get("version", "")),
        apiKeyMasked=_mask_api_key(str(v.get("apiKey", "") or "")),
    ).model_dump()

    return ok(data=data, request_id=request.state.request_id)


class AdminPutAiConfigBody(BaseModel):
    enabled: bool | None = None
    provider: Literal["OPENAI_COMPAT"] | None = None
    baseUrl: str | None = None
    apiKey: str | None = None
    model: str | None = None
    systemPrompt: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    maxTokens: int | None = Field(default=None, ge=1, le=200000)
    timeoutMs: int | None = Field(default=None, ge=100, le=120000)
    retries: int | None = Field(default=None, ge=0, le=10)
    rateLimitPerMinute: int | None = Field(default=None, ge=1, le=100000)


@router.put("/admin/ai/config")
async def admin_put_ai_config(
    request: Request,
    body: AdminPutAiConfigBody,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_ai_config(session)
        v = _normalize_value(cfg.value_json)

        # provider v1 固定 OPENAI_COMPAT
        if body.provider is not None and body.provider != "OPENAI_COMPAT":
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "provider 不支持"})

        def _strip(s: str | None) -> str | None:
            if s is None:
                return None
            return s.strip()

        if body.enabled is not None:
            v["enabled"] = bool(body.enabled)
        if body.baseUrl is not None:
            v["baseUrl"] = _strip(body.baseUrl) or ""
        if body.model is not None:
            v["model"] = _strip(body.model) or ""
        if body.systemPrompt is not None:
            v["systemPrompt"] = body.systemPrompt
        if body.temperature is not None:
            v["temperature"] = float(body.temperature)
        if body.maxTokens is not None:
            v["maxTokens"] = int(body.maxTokens)
        if body.timeoutMs is not None:
            v["timeoutMs"] = int(body.timeoutMs)
        if body.retries is not None:
            v["retries"] = int(body.retries)
        if body.rateLimitPerMinute is not None:
            v["rateLimitPerMinute"] = int(body.rateLimitPerMinute)

        # apiKey：允许可选更新；空字符串视为“不更新”
        if body.apiKey is not None:
            key = body.apiKey.strip()
            if key:
                v["apiKey"] = key

        # 写入新版本号
        v["version"] = _now_version()

        cfg.value_json = v
        await session.commit()

    # 返回脱敏后的配置
    return await admin_get_ai_config(request=request, authorization=authorization)


# -----------------------------
# Admin：AI 调用审计日志（阶段11）
# -----------------------------


@router.get("/admin/ai/audit-logs")
async def admin_list_ai_audit_logs(
    request: Request,
    authorization: str | None = Header(default=None),
    userId: str | None = None,
    resultStatus: Literal["success", "fail"] | None = None,
    provider: str | None = None,
    model: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    await _require_admin(authorization)

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    # v1：基于 audit_logs 过滤 resourceType="AI_CHAT" 聚合生成（不存储对话内容）
    stmt = select(AuditLog).where(AuditLog.resource_type == "AI_CHAT")

    if userId and userId.strip():
        stmt = stmt.where(AuditLog.actor_id == userId.strip())

    def _json_str(field: str):
        # mysql JSON：json_extract + json_unquote
        return func.json_unquote(func.json_extract(AuditLog.metadata_json, f"$.{field}"))

    if resultStatus:
        stmt = stmt.where(_json_str("resultStatus") == str(resultStatus))
    if provider and provider.strip():
        stmt = stmt.where(_json_str("provider") == provider.strip())
    if model and model.strip():
        stmt = stmt.where(_json_str("model") == model.strip())

    if dateFrom:
        stmt = stmt.where(AuditLog.created_at >= _parse_dt(str(dateFrom), field_name="dateFrom"))
    if dateTo:
        stmt = stmt.where(AuditLog.created_at <= _parse_dt(str(dateTo), field_name="dateTo"))

    stmt = stmt.order_by(AuditLog.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        logs = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items: list[dict] = []
    for x in logs:
        meta = x.metadata_json or {}
        items.append(
            {
                "userId": str(meta.get("userId") or x.actor_id),
                "timestamp": x.created_at.astimezone().isoformat(),
                "provider": str(meta.get("provider") or ""),
                "model": str(meta.get("model") or ""),
                "latencyMs": int(meta.get("latencyMs") or 0),
                "resultStatus": str(meta.get("resultStatus") or ""),
                "errorCode": (str(meta.get("errorCode")) if meta.get("errorCode") else None),
                "configVersion": (str(meta.get("configVersion")) if meta.get("configVersion") else None),
            }
        )

    return ok(
        data={"items": items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )

