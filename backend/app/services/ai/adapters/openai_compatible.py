"""OpenAPI compatible (OpenAI Chat Completions compatible) adapter."""

from __future__ import annotations

import time

import httpx
from fastapi import HTTPException

from app.services.ai.adapters.base import ProviderAdapter
from app.services.ai.prompting import build_system_prompt
from app.services.ai.types import AiAdapterResult, AiCallContext, AiProviderSnapshot, AiStrategySnapshot


class OpenAiCompatibleAdapter(ProviderAdapter):
    def supports(self, *, strategy: AiStrategySnapshot) -> bool:
        _ = strategy
        return True

    async def execute(
        self,
        *,
        provider: AiProviderSnapshot,
        strategy: AiStrategySnapshot,
        user_input: str,
        context: AiCallContext,
    ) -> AiAdapterResult:
        _ = context

        endpoint = (provider.endpoint or "").strip()
        api_key = str((provider.credentials or {}).get("api_key") or (provider.credentials or {}).get("apiKey") or "").strip()
        model = str((provider.extra or {}).get("default_model") or (provider.extra or {}).get("model") or "").strip()

        if not endpoint:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI Provider endpoint 未配置"})
        if not api_key:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI Provider 凭证未配置"})
        if not model:
            # OpenAI compatible 需要 model（放在 Provider.extra，避免污染 Strategy）
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI Provider default_model 未配置"})

        url = endpoint.rstrip("/") + "/v1/chat/completions"

        gen = dict(strategy.generation_config or {})
        temperature = gen.get("temperature", None)
        max_output_tokens = gen.get("max_output_tokens", None)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": build_system_prompt(prompt_template=strategy.prompt_template, constraints=strategy.constraints)},
                {"role": "user", "content": str(user_input or "").strip()},
            ],
        }
        if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
            payload["temperature"] = float(temperature)
        if isinstance(max_output_tokens, (int, float)) and not isinstance(max_output_tokens, bool):
            payload["max_tokens"] = int(max_output_tokens)

        timeout_ms = int((provider.extra or {}).get("timeoutMs") or 15000)
        retries = int((provider.extra or {}).get("retries") or 1)
        timeout_s = max(0.1, float(timeout_ms) / 1000.0)

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        max_attempts = 1 + max(0, retries)
        last_exc: Exception | None = None
        started = time.perf_counter()

        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code >= 500 and attempt < max_attempts - 1:
                    continue
                data = resp.json()
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=500,
                        detail={"code": "INTERNAL_ERROR", "message": "AI 服务调用失败", "details": {"status": resp.status_code}},
                    )

                content = (data.get("choices") or [{}])[0].get("message", {}).get("content") if isinstance(data, dict) else None
                if not content or not str(content).strip():
                    raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "AI 服务返回异常"})

                latency_ms = int((time.perf_counter() - started) * 1000)
                return AiAdapterResult(content=str(content).strip(), provider_latency_ms=latency_ms, raw=None)
            except HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < max_attempts - 1:
                    continue
                break

        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "AI 服务调用失败"}) from last_exc

