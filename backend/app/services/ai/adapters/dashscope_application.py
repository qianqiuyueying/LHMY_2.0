"""DashScope 应用模式 adapter（HTTP）。

规格来源：
- specs/health-services-platform/ai-gateway-v2.md -> DashScope 特别说明（应用模式）

接口参考（公开文档）：
- POST {endpoint}/api/v1/apps/{app_id}/completion
  - Authorization: Bearer {api_key}
  - body: { "input": { "prompt": "..." }, "parameters": {...} }
"""

from __future__ import annotations

import time

import httpx
from fastapi import HTTPException

from app.services.ai.adapters.base import ProviderAdapter
from app.services.ai.prompting import build_single_turn_prompt
from app.services.ai.types import AiAdapterResult, AiCallContext, AiProviderSnapshot, AiStrategySnapshot


class DashScopeApplicationAdapter(ProviderAdapter):
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

        api_key = str((provider.credentials or {}).get("api_key") or (provider.credentials or {}).get("apiKey") or "").strip()
        app_id = str((provider.credentials or {}).get("app_id") or (provider.credentials or {}).get("appId") or "").strip()
        endpoint = (provider.endpoint or "").strip() or "https://dashscope.aliyuncs.com"

        if not api_key or not app_id:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI Provider 凭证未配置"})

        url = endpoint.rstrip("/") + f"/api/v1/apps/{app_id}/completion"

        gen = dict(strategy.generation_config or {})
        temperature = gen.get("temperature", None)
        max_output_tokens = gen.get("max_output_tokens", None)

        prompt = build_single_turn_prompt(
            prompt_template=strategy.prompt_template, user_message=str(user_input or "").strip(), constraints=strategy.constraints
        )

        parameters: dict = {}
        if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
            parameters["temperature"] = float(temperature)
        if isinstance(max_output_tokens, (int, float)) and not isinstance(max_output_tokens, bool):
            parameters["max_tokens"] = int(max_output_tokens)
        # 允许运营/管理员通过 Provider.extra 传入 app 级参数（provider 私有解释，不进入 Strategy）
        extra_params = (provider.extra or {}).get("app_parameters")
        if isinstance(extra_params, dict):
            parameters.update(extra_params)

        payload = {"input": {"prompt": prompt}}
        if parameters:
            payload["parameters"] = parameters

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

                # 兼容：不同 app 的 output 结构可能不同；优先按 output.text / output.answer 取
                out = data.get("output") if isinstance(data, dict) else None
                content = None
                if isinstance(out, dict):
                    content = out.get("text") or out.get("answer") or out.get("content")
                if not content:
                    # 再兜底：常见字段
                    content = data.get("text") if isinstance(data, dict) else None
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

