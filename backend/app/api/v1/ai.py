"""AI 网关（v2：Provider/Strategy/Gateway）。

规格来源（单一真相来源）：
- specs/health-services-platform/ai-gateway-v2.md

约束（继承 v1 的运行门禁）：
- 必须登录（USER token）
- 写操作必须幂等（Idempotency-Key）
- 不持久化对话内容（不落库 messages）
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.ai_provider import AiProvider
from app.models.ai_strategy import AiStrategy
from app.models.enums import AuditAction, AuditActorType
from app.services.idempotency import IdempotencyCachedResult, IdempotencyService
from app.services.ai.gateway import call_ai
from app.services.ai.types import AiCallContext
from app.utils.db import get_session_factory
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.redis_client import get_redis
from app.utils.response import ok
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["ai"])

def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return idempotency_key.strip()


def _user_id_from_authorization(authorization: str | None) -> str:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token)
    return str(payload["sub"])




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


class AiChatBody(BaseModel):
    scene: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=20000)


class AiChatResp(BaseModel):
    message: dict
    scene: str


async def _audit_ai_call(
    *,
    user_id: str,
    provider: str,
    model: str,
    scene: str,
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
            "scene": str(scene),
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

    scene = str(body.scene or "").strip()
    user_message = str(body.message or "").strip()

    started = time.perf_counter()
    error_code: str | None = None
    provider_for_audit = ""
    model_for_audit = ""
    config_version: str | None = None
    try:
        # v2：频控（按用户维度），limit 来自 Provider.extra.rateLimitPerMinute（缺省 30）
        limit_per_minute = 30
        session_factory = get_session_factory()
        async with session_factory() as session:
            st = (await session.scalars(select(AiStrategy).where(AiStrategy.scene == scene).limit(1))).first()
            if st is not None and st.provider_id:
                pv = (await session.scalars(select(AiProvider).where(AiProvider.id == st.provider_id).limit(1))).first()
                if pv is not None:
                    try:
                        limit_per_minute = int((pv.extra_json or {}).get("rateLimitPerMinute") or 30)
                    except Exception:  # noqa: BLE001
                        limit_per_minute = 30
        await _rate_limit_or_raise(user_id=user_id, limit_per_minute=limit_per_minute)

        gw = await call_ai(
            scene=scene,
            user_input=user_message,
            context=AiCallContext(user_id=user_id, request_id=request.state.request_id),
        )
        cost_ms = int((time.perf_counter() - started) * 1000)
        provider_for_audit = str(gw.provider.provider_type or "")
        model_for_audit = str((gw.provider.extra or {}).get("default_model") or "")
        await _audit_ai_call(
            user_id=user_id,
            provider=provider_for_audit,
            model=model_for_audit,
            scene=scene,
            latency_ms=cost_ms,
            result_status="success",
            error_code=None,
            config_version=config_version,
            request=request,
        )

        data = AiChatResp(
            message={"role": "assistant", "content": gw.content},
            scene=scene,
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
                provider=provider_for_audit or "",
                model=model_for_audit or "",
                scene=scene,
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
