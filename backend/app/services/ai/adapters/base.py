"""Provider Adapter 规范（v2，强制）。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.ai.types import AiAdapterResult, AiCallContext, AiProviderSnapshot, AiStrategySnapshot


class ProviderAdapter(ABC):
    @abstractmethod
    def supports(self, *, strategy: AiStrategySnapshot) -> bool:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    async def execute(
        self,
        *,
        provider: AiProviderSnapshot,
        strategy: AiStrategySnapshot,
        user_input: str,
        context: AiCallContext,
    ) -> AiAdapterResult:  # pragma: no cover
        raise NotImplementedError

