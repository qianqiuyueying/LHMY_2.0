"""AI 网关（阶段11，v1 最小可执行）。

规格来源（已确认）：
- specs/health-services-platform/design.md -> AI 对话能力（中转模式/稳定性/审计字段示例）
- specs/health-services-platform/tasks.md -> 阶段11「规格补充（待确认）」-> 用户已确认

约束：
- 必须登录（USER token）
- 不持久化对话内容（不落库 messages）
- Provider 协议固定 OPENAI_COMPAT：`${baseUrl}/v1/chat/completions`
- 停用/配置缺失：FORBIDDEN(403) + message 明确原因
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType, CommonEnabledStatus
from app.models.system_config import SystemConfig
from app.services.idempotency import IdempotencyCachedResult, IdempotencyService
from app.utils.db import get_session_factory
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.redis_client import get_redis
from app.utils.response import ok
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["ai"])

_KEY_AI_CONFIG = "AI_CONFIG"

def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return idempotency_key.strip()


def _user_id_from_authorization(authorization: str | None) -> str:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token)
    return str(payload["sub"])


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
        "version": str(int(time.time())),
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


def _normalize_cfg(value: dict) -> dict:
    v = dict(value or {})
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
    v.setdefault("version", str(int(time.time())))
    return v


async def _rate_limit_or_raise(*, user_id: str, limit_per_minute: int) -> None:
    limit = max(1, int(limit_per_minute))
    now = int(time.time())
    bucket = now // 60
    key = f"ai:rl:{user_id}:{bucket}"
    redis = get_redis()
    n = int(await redis.incr(key))
    # 第一次命中设置 TTL
    if n == 1:
        await redis.expire(key, 120)
    if n > limit:
        raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "AI 调用频率过高，请稍后再试"})


class AiMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1, max_length=20000)


class AiChatBody(BaseModel):
    messages: list[AiMessage] = Field(..., min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    maxTokens: int | None = Field(default=None, ge=1, le=200000)


class AiChatResp(BaseModel):
    message: dict
    provider: str
    model: str


async def _audit_ai_call(
    *,
    user_id: str,
    provider: str,
    model: str,
    latency_ms: int,
    result_status: Literal["success", "fail"],
    error_code: str | None,
    config_version: str | None,
    request: Request,
) -> None:
    # 仅记录元数据，不记录对话内容
    log = AuditLog(
        id=str(uuid4()),
        actor_type=AuditActorType.USER.value,
        actor_id=str(user_id),
        action=AuditAction.CREATE.value,
        resource_type="AI_CHAT",
        resource_id=None,
        summary=f"AI_CHAT {result_status}",
        ip=getattr(getattr(request, "client", None), "host", None),
        user_agent=request.headers.get("User-Agent"),
        metadata_json={
            "userId": str(user_id),
            "timestamp": int(time.time()),
            "provider": str(provider),
            "model": str(model),
            "latencyMs": int(latency_ms),
            "resultStatus": str(result_status),
            "errorCode": (str(error_code) if error_code else None),
            "configVersion": (str(config_version) if config_version else None),
            "requestId": getattr(request.state, "request_id", ""),
        },
        created_at=datetime.utcnow(),
    )
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(log)
        await session.commit()


async def _openai_compat_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
    timeout_ms: int,
    retries: int,
) -> tuple[str, int]:
    url = base_url.rstrip("/") + "/v1/chat/completions"

    final_messages = list(messages)
    if system_prompt and system_prompt.strip():
        # v1：将 systemPrompt 作为首条 system message 注入
        final_messages = [{"role": "system", "content": system_prompt.strip()}] + final_messages

    payload = {
        "model": model,
        "messages": final_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    timeout_s = max(0.1, float(timeout_ms) / 1000.0)
    max_attempts = 1 + max(0, int(retries))
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(url, json=payload, headers=headers)
            # 仅对 5xx 重试；4xx 直接失败
            if resp.status_code >= 500 and attempt < max_attempts - 1:
                continue
            data = resp.json()
            if resp.status_code != 200:
                # 兼容返回结构：尽量提取错误信息但不对外透传
                raise HTTPException(
                    status_code=500,
                    detail={
                        "code": "INTERNAL_ERROR",
                        "message": "AI 服务调用失败",
                        "details": {"status": resp.status_code},
                    },
                )

            content = (
                (data.get("choices") or [{}])[0].get("message", {}).get("content") if isinstance(data, dict) else None
            )
            if not content or not str(content).strip():
                raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "AI 服务返回异常"})
            return str(content), int(resp.elapsed.total_seconds() * 1000)
        except HTTPException:
            # 已包装为 INTERNAL_ERROR
            raise
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < max_attempts - 1:
                continue
            break

    raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "AI 服务调用失败"}) from last_exc


@router.post("/ai/chat")
async def ai_chat(
    request: Request,
    body: AiChatBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    # v1：必须登录
    user_id = _user_id_from_authorization(authorization)

    # v1：对 chat 也支持幂等（避免前端重试造成重复计费/重复调用）
    idem_key = _require_idempotency_key(idempotency_key)
    idem = IdempotencyService(get_redis())
    cached = await idem.get(operation="ai_chat", actor_type="USER", actor_id=user_id, idempotency_key=idem_key)
    if cached is not None:
        # 复用 orders.py 的口径：data/error 复用，但 requestId 为当前请求
        if cached.success:
            return ok(data=cached.data, request_id=request.state.request_id)
        err = cached.error or {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "details": None}
        raise HTTPException(status_code=int(cached.status_code), detail=err)

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_ai_config(session)
        v = _normalize_cfg(cfg.value_json)

    if not bool(v.get("enabled", False)):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI 功能已停用"})
    if str(v.get("provider", "") or "") != "OPENAI_COMPAT":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI Provider 配置不支持"})

    base_url = str(v.get("baseUrl", "") or "").strip()
    api_key = str(v.get("apiKey", "") or "").strip()
    model = str(v.get("model", "") or "").strip()
    if not base_url or not api_key or not model:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI 配置不完整"})

    # 频控（按用户维度）
    await _rate_limit_or_raise(user_id=user_id, limit_per_minute=int(v.get("rateLimitPerMinute", 30)))

    temperature = float(body.temperature) if body.temperature is not None else float(v.get("temperature", 0.7))
    max_tokens = int(body.maxTokens) if body.maxTokens is not None else int(v.get("maxTokens", 1024))
    timeout_ms = int(v.get("timeoutMs", 15000))
    retries = int(v.get("retries", 1))
    system_prompt = str(v.get("systemPrompt", "") or "").strip() or None
    config_version = str(v.get("version", "") or "") or None

    messages = [m.model_dump() for m in body.messages]

    started = time.perf_counter()
    error_code: str | None = None
    try:
        content, _provider_latency_ms = await _openai_compat_chat(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_ms=timeout_ms,
            retries=retries,
        )
        cost_ms = int((time.perf_counter() - started) * 1000)
        # 优先用本地耗时（包含重试），provider_latency_ms 仅供参考
        await _audit_ai_call(
            user_id=user_id,
            provider="OPENAI_COMPAT",
            model=model,
            latency_ms=cost_ms,
            result_status="success",
            error_code=None,
            config_version=config_version,
            request=request,
        )

        data = AiChatResp(
            message={"role": "assistant", "content": content}, provider="OPENAI_COMPAT", model=model
        ).model_dump()
        await idem.set(
            operation="ai_chat",
            actor_type="USER",
            actor_id=user_id,
            idempotency_key=idem_key,
            result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
        )
        return ok(data=data, request_id=request.state.request_id)
    except HTTPException as exc:
        cost_ms = int((time.perf_counter() - started) * 1000)
        detail: dict[str, object] = exc.detail if isinstance(exc.detail, dict) else {}
        error_code = str(detail.get("code") or "INTERNAL_ERROR")

        # 仅对“调用失败”记录 fail；停用/未登录/限流属于前置校验，不记为调用 fail（避免噪音）
        if exc.status_code >= 500:
            await _audit_ai_call(
                user_id=user_id,
                provider="OPENAI_COMPAT",
                model=model or "",
                latency_ms=cost_ms,
                result_status="fail",
                error_code=error_code,
                config_version=config_version,
                request=request,
            )
            await idem.set(
                operation="ai_chat",
                actor_type="USER",
                actor_id=user_id,
                idempotency_key=idem_key,
                result=IdempotencyCachedResult(
                    status_code=int(exc.status_code),
                    success=False,
                    data=None,
                    error={
                        "code": error_code,
                        "message": str(detail.get("message") or "AI 服务调用失败"),
                        "details": None,
                    },
                ),
            )
        raise
