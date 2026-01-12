"""AI Gateway（v2 统一入口）。"""

from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import HTTPException

from app.services.ai.factory import create_adapter
from app.services.ai.repository import load_provider_by_id, load_strategy_by_scene
from app.services.ai.risk import is_medical_diagnosis_request, refusal_for_diagnosis
from app.services.ai.types import AiAdapterResult, AiCallContext, AiProviderSnapshot, AiStrategySnapshot
from app.utils.db import get_session_factory


@dataclass(frozen=True)
class AiGatewayResult:
    content: str
    provider: AiProviderSnapshot
    strategy: AiStrategySnapshot
    provider_latency_ms: int | None


async def call_ai(*, scene: str, user_input: str, context: AiCallContext) -> AiGatewayResult:
    scene = str(scene or "").strip()
    if not scene:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 scene"})

    user_input = str(user_input or "").strip()
    if not user_input:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 message"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        strategy = await load_strategy_by_scene(session, scene=scene)
        if strategy is None:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"AI 场景未配置或已停用（scene={scene}）。请在管理后台创建并启用对应 AI Strategy。",
                },
            )

        # 风控：诊断类问题直接拒答，不调用第三方
        if bool((strategy.constraints or {}).get("forbid_medical_diagnosis")) and is_medical_diagnosis_request(user_input):
            return AiGatewayResult(
                content=refusal_for_diagnosis(),
                provider=AiProviderSnapshot(id="", name="", provider_type="RISK_BLOCKED", credentials={}, endpoint=None, extra={}),
                strategy=strategy,
                provider_latency_ms=0,
            )

        provider_id = str(strategy.provider_id or "").strip()
        if not provider_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"AI 场景未绑定 Provider（scene={scene}）。请在管理后台“AI 绑定关系”把该 scene 绑定到一个 Provider。",
                },
            )

        provider = await load_provider_by_id(session, provider_id=provider_id)
        if provider is None:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"AI Provider 未配置或已停用（scene={scene}）。请检查绑定的 Provider 是否存在且状态为 ENABLED。",
                },
            )

    adapter = create_adapter(provider)
    if not adapter.supports(strategy=strategy):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI Provider 不支持该场景"})

    started = time.perf_counter()
    result: AiAdapterResult = await adapter.execute(provider=provider, strategy=strategy, user_input=user_input, context=context)
    latency_ms = int((time.perf_counter() - started) * 1000)
    provider_latency = result.provider_latency_ms if result.provider_latency_ms is not None else latency_ms
    return AiGatewayResult(content=str(result.content).strip(), provider=provider, strategy=strategy, provider_latency_ms=provider_latency)

