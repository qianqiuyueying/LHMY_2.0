"""Admin AI 配置中心（阶段11，v1 最小可执行）。

规格来源（已确认）：
- specs/health-services-platform/design.md -> AI 对话能力（配置项/审计元数据）
- specs/health-services-platform/tasks.md -> 阶段11「规格补充（待确认）」-> 用户已确认

存储承载：
- SystemConfig.key = "AI_CONFIG"
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType, CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.services.idempotency import IdemActorType, IdempotencyCachedResult, IdempotencyService
from app.utils.redis_client import get_redis
from app.utils.db import get_session_factory
from app.utils.response import fail, ok
from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.services.rbac import ActorContext
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-ai"])

_KEY_AI_CONFIG = "AI_CONFIG"
_OPERATION_PUT_AI_CONFIG = "ADMIN_PUT_AI_CONFIG"


def _now_version() -> str:
    return str(int(time.time()))


_TZ_BEIJING = timezone(timedelta(hours=8))


def _parse_beijing_day(raw: str, *, field_name: str) -> date:
    try:
        if len(raw) != 10:
            raise ValueError("expected YYYY-MM-DD")
        return date.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}
        ) from exc


def _beijing_day_range_to_utc_naive(d: date) -> tuple[datetime, datetime]:
    start_bj = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    next_day = d + timedelta(days=1)
    end_bj_exclusive = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    return (
        start_bj.astimezone(timezone.utc).replace(tzinfo=None),
        end_bj_exclusive.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _mask_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    s = str(api_key).strip()
    if len(s) <= 8:
        return "****"
    return f"{s[:3]}****{s[-4:]}"


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not str(idempotency_key).strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return str(idempotency_key).strip()


async def _idempotency_replay_if_exists(
    *,
    request: Request,
    operation: str,
    actor_type: IdemActorType,
    actor_id: str,
    idempotency_key: str,
) -> JSONResponse | None:
    idem = IdempotencyService(get_redis())
    cached = await idem.get(operation=operation, actor_type=actor_type, actor_id=actor_id, idempotency_key=idempotency_key)
    if cached is None:
        return None

    if cached.success:
        payload = ok(data=cached.data, request_id=request.state.request_id)
    else:
        err = cached.error or {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "details": None}
        payload = fail(
            code=str(err.get("code", "INTERNAL_ERROR")),
            message=str(err.get("message", "服务器内部错误")),
            details=err.get("details"),
            request_id=request.state.request_id,
        )
    return JSONResponse(status_code=int(cached.status_code), content=payload)


def _ai_config_public_view(value_json: dict) -> dict:
    v = _normalize_value(value_json)
    return {
        "enabled": bool(v.get("enabled", False)),
        "provider": "OPENAI_COMPAT",
        "baseUrl": str(v.get("baseUrl", "") or ""),
        "model": str(v.get("model", "") or ""),
        "systemPrompt": (str(v.get("systemPrompt")) if v.get("systemPrompt") is not None else None),
        "temperature": (float(v["temperature"]) if v.get("temperature") is not None else None),
        "maxTokens": (int(v["maxTokens"]) if v.get("maxTokens") is not None else None),
        "timeoutMs": (int(v["timeoutMs"]) if v.get("timeoutMs") is not None else None),
        "retries": (int(v["retries"]) if v.get("retries") is not None else None),
        "rateLimitPerMinute": (int(v["rateLimitPerMinute"]) if v.get("rateLimitPerMinute") is not None else None),
        "version": str(v.get("version", "")),
        "apiKeyMasked": _mask_api_key(str(v.get("apiKey", "") or "")),
    }


def _ai_config_audit_view(value_json: dict) -> dict:
    """用于审计 before/after：禁止包含 apiKey 明文。"""
    v = _normalize_value(value_json)
    return {
        "enabled": bool(v.get("enabled", False)),
        "provider": "OPENAI_COMPAT",
        "baseUrl": str(v.get("baseUrl", "") or ""),
        "model": str(v.get("model", "") or ""),
        "systemPrompt": str(v.get("systemPrompt", "") or ""),
        "temperature": float(v.get("temperature", 0.7)),
        "maxTokens": int(v.get("maxTokens", 1024)),
        "timeoutMs": int(v.get("timeoutMs", 15000)),
        "retries": int(v.get("retries", 1)),
        "rateLimitPerMinute": int(v.get("rateLimitPerMinute", 30)),
        "version": str(v.get("version", "")),
    }



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
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}
        ) from exc


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
    _admin: ActorContext = Depends(require_admin),
):
    _ = _admin

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_ai_config(session)
        data = AdminAiConfigResp(**_ai_config_public_view(cfg.value_json)).model_dump()

    return ok(data=data, request_id=request.state.request_id)

@router.put("/admin/ai/config")
async def admin_put_ai_config(
    request: Request,
    body: dict[str, Any] = Body(default_factory=dict),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation=_OPERATION_PUT_AI_CONFIG,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_ai_config(session)
        before_raw = _normalize_value(cfg.value_json)
        before_audit = _ai_config_audit_view(before_raw)
        v = dict(before_raw)

        def _opt_bool(field: str) -> bool | None:
            if field not in body:
                return None
            val = body.get(field)
            if val is None:
                return None
            if isinstance(val, bool):
                return val
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field} 必须是 boolean"})

        def _opt_str(field: str) -> str | None:
            if field not in body:
                return None
            val = body.get(field)
            if val is None:
                return None
            if not isinstance(val, str):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field} 必须是 string"})
            return val

        def _opt_int(field: str, *, ge: int, le: int) -> int | None:
            if field not in body:
                return None
            val = body.get(field)
            if val is None:
                return None
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field} 必须是 number"})
            n = int(val)
            if n < ge or n > le:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field} 范围不合法"})
            return n

        def _opt_float(field: str, *, ge: float, le: float) -> float | None:
            if field not in body:
                return None
            val = body.get(field)
            if val is None:
                return None
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field} 必须是 number"})
            n = float(val)
            if n < ge or n > le:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field} 范围不合法"})
            return n

        # provider v1 固定 OPENAI_COMPAT
        provider = _opt_str("provider")
        if provider is not None and provider.strip() and provider.strip() != "OPENAI_COMPAT":
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "provider 不支持"})

        enabled = _opt_bool("enabled")
        base_url = _opt_str("baseUrl")
        model = _opt_str("model")
        system_prompt = _opt_str("systemPrompt")
        temperature = _opt_float("temperature", ge=0.0, le=2.0)
        max_tokens = _opt_int("maxTokens", ge=1, le=200000)
        timeout_ms = _opt_int("timeoutMs", ge=100, le=120000)
        retries = _opt_int("retries", ge=0, le=10)
        rate_limit = _opt_int("rateLimitPerMinute", ge=1, le=100000)
        api_key_raw = _opt_str("apiKey")

        changed_fields: list[str] = []
        api_key_updated = False

        if enabled is not None and bool(enabled) != bool(v.get("enabled", False)):
            v["enabled"] = bool(enabled)
            changed_fields.append("enabled")
        if base_url is not None:
            new_val = base_url.strip()
            if new_val != str(v.get("baseUrl", "") or ""):
                v["baseUrl"] = new_val
                changed_fields.append("baseUrl")
        if model is not None:
            new_val = model.strip()
            if new_val != str(v.get("model", "") or ""):
                v["model"] = new_val
                changed_fields.append("model")
        if system_prompt is not None:
            if system_prompt != str(v.get("systemPrompt", "") or ""):
                v["systemPrompt"] = system_prompt
                changed_fields.append("systemPrompt")
        if temperature is not None and float(temperature) != float(v.get("temperature", 0.7)):
            v["temperature"] = float(temperature)
            changed_fields.append("temperature")
        if max_tokens is not None and int(max_tokens) != int(v.get("maxTokens", 1024)):
            v["maxTokens"] = int(max_tokens)
            changed_fields.append("maxTokens")
        if timeout_ms is not None and int(timeout_ms) != int(v.get("timeoutMs", 15000)):
            v["timeoutMs"] = int(timeout_ms)
            changed_fields.append("timeoutMs")
        if retries is not None and int(retries) != int(v.get("retries", 1)):
            v["retries"] = int(retries)
            changed_fields.append("retries")
        if rate_limit is not None and int(rate_limit) != int(v.get("rateLimitPerMinute", 30)):
            v["rateLimitPerMinute"] = int(rate_limit)
            changed_fields.append("rateLimitPerMinute")

        # apiKey：允许可选更新；空字符串视为“不更新”；同值更新视为 no-op
        if api_key_raw is not None:
            key = api_key_raw.strip()
            if key:
                before_key = str(v.get("apiKey", "") or "")
                if key != before_key:
                    v["apiKey"] = key
                    changed_fields.append("apiKey")
                    api_key_updated = True

        if changed_fields:
            # 版本号：仅在“实际变更”时变化；避免同秒内更新产生相同 version
            new_version = _now_version()
            if str(v.get("version", "")) == str(new_version):
                try:
                    new_version = str(int(new_version) + 1)
                except Exception:  # noqa: BLE001
                    new_version = f"{new_version}-1"
            v["version"] = new_version
            after_audit = _ai_config_audit_view(v)

            cfg.value_json = v
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.ADMIN.value,
                    actor_id=admin_id,
                    action=AuditAction.UPDATE.value,
                    resource_type="AI_CONFIG",
                    resource_id=_KEY_AI_CONFIG,
                    summary="ADMIN 更新 AI 配置",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={
                        "requestId": request.state.request_id,
                        "resourceKey": _KEY_AI_CONFIG,
                        "changedFields": changed_fields,
                        "apiKeyUpdated": api_key_updated,
                        "before": before_audit,
                        "after": after_audit,
                    },
                )
            )
            await session.commit()
        else:
            # no-op：不 bump version，不写审计
            await session.commit()

    data = AdminAiConfigResp(**_ai_config_public_view(v)).model_dump()
    payload = ok(data=data, request_id=request.state.request_id)
    await IdempotencyService(get_redis()).set(
        operation=_OPERATION_PUT_AI_CONFIG,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return payload


# -----------------------------
# Admin：AI 调用审计日志（阶段11）
# -----------------------------


@router.get("/admin/ai/audit-logs")
async def admin_list_ai_audit_logs(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    userId: str | None = None,
    resultStatus: Literal["success", "fail"] | None = None,
    provider: str | None = None,
    model: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

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

    # Spec (Admin): dateFrom/dateTo are Beijing natural days (YYYY-MM-DD)
    if dateFrom:
        d_from = _parse_beijing_day(str(dateFrom), field_name="dateFrom")
        start_utc, _end_exclusive = _beijing_day_range_to_utc_naive(d_from)
        stmt = stmt.where(AuditLog.created_at >= start_utc)
    if dateTo:
        d_to = _parse_beijing_day(str(dateTo), field_name="dateTo")
        _start_utc, end_exclusive = _beijing_day_range_to_utc_naive(d_to)
        stmt = stmt.where(AuditLog.created_at < end_exclusive)

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
                "timestamp": _iso(x.created_at),
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
