"""AI 服务内部类型（v2）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class AiStrategySnapshot:
    scene: str
    display_name: str
    provider_id: str | None
    prompt_template: str
    generation_config: dict[str, Any]
    constraints: dict[str, Any]


@dataclass(frozen=True)
class AiProviderSnapshot:
    id: str
    name: str
    provider_type: str
    credentials: dict[str, Any]
    endpoint: str | None
    extra: dict[str, Any]


@dataclass(frozen=True)
class AiCallContext:
    user_id: str
    request_id: str


@dataclass(frozen=True)
class AiAdapterResult:
    content: str
    # 对 admin 审计/排障友好，但禁止返回给小程序端
    provider_latency_ms: int | None = None
    raw: dict[str, Any] | None = None


AiResultStatus = Literal["success", "fail"]

