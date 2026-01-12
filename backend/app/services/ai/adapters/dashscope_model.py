"""DashScope 模型模式 adapter（HTTP）。

规格来源：
- specs/health-services-platform/ai-gateway-v2.md -> DashScope 特别说明（模型模式）

接口参考（公开文档）：
- POST {endpoint}/api/v1/services/aigc/text-generation/generation
  - Authorization: Bearer {api_key}
  - body:
    {
      "model": "<model>",
      "input": { "messages": [...] },
      "parameters": { "result_format": "message", ... }
    }
"""

from __future__ import annotations

import time

import httpx
from fastapi import HTTPException

from app.services.ai.adapters.base import ProviderAdapter
from app.services.ai.prompting import build_system_prompt
from app.services.ai.types import AiAdapterResult, AiCallContext, AiProviderSnapshot, AiStrategySnapshot


class DashScopeModelAdapter(ProviderAdapter):
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
        endpoint = (provider.endpoint or "").strip() or "https://dashscope.aliyuncs.com"
        model = str((provider.extra or {}).get("default_model") or (provider.extra or {}).get("model") or "").strip()

        if not api_key:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI Provider 凭证未配置"})
        if not model:
            # DashScope 模型模式需要 model，但必须放在 Provider.extra（避免污染 Strategy）
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI Provider default_model 未配置"})

        url = endpoint.rstrip("/") + "/api/v1/services/aigc/text-generation/generation"

        gen = dict(strategy.generation_config or {})
        temperature = gen.get("temperature", None)
        max_output_tokens = gen.get("max_output_tokens", None)

        parameters: dict = {"result_format": "message"}
        if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
            parameters["temperature"] = float(temperature)
        if isinstance(max_output_tokens, (int, float)) and not isinstance(max_output_tokens, bool):
            # DashScope 常用字段为 max_tokens（与 OpenAI 不同，但属于 adapter 内部适配）
            parameters["max_tokens"] = int(max_output_tokens)

        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "system",
                        "content": build_system_prompt(
                            prompt_template=strategy.prompt_template, constraints=strategy.constraints
                        ),
                    },
                    {"role": "user", "content": str(user_input or "").strip()},
                ]
            },
            "parameters": parameters,
        }

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

                # result_format=message 时，常见结构为 output.choices[0].message.content
                out = data.get("output") if isinstance(data, dict) else None
                content = None
                if isinstance(out, dict):
                    choices = out.get("choices") or []
                    if isinstance(choices, list) and choices:
                        msg = (choices[0] or {}).get("message") if isinstance(choices[0], dict) else None
                        if isinstance(msg, dict):
                            content = msg.get("content")
                    if not content:
                        # 兜底：output.text
                        content = out.get("text")
                if not content and isinstance(data, dict):
                    content = data.get("text")

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

