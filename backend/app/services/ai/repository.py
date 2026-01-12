"""AI Provider/Strategy 读取（v2）。"""

from __future__ import annotations

from sqlalchemy import select

from app.models.ai_provider import AiProvider
from app.models.ai_strategy import AiStrategy
from app.models.enums import CommonEnabledStatus
from app.services.ai.types import AiProviderSnapshot, AiStrategySnapshot


def _enabled(v: str | None) -> bool:
    return str(v or "") == CommonEnabledStatus.ENABLED.value


async def load_strategy_by_scene(session, *, scene: str) -> AiStrategySnapshot | None:
    row = (await session.scalars(select(AiStrategy).where(AiStrategy.scene == scene).limit(1))).first()
    if row is None or not _enabled(row.status):
        return None
    return AiStrategySnapshot(
        scene=str(row.scene),
        display_name=str(row.display_name or ""),
        provider_id=(str(row.provider_id) if row.provider_id else None),
        prompt_template=str(row.prompt_template or ""),
        generation_config=dict(row.generation_config_json or {}),
        constraints=dict(row.constraints_json or {}),
    )


async def load_provider_by_id(session, *, provider_id: str) -> AiProviderSnapshot | None:
    row = (await session.scalars(select(AiProvider).where(AiProvider.id == provider_id).limit(1))).first()
    if row is None or not _enabled(row.status):
        return None
    return AiProviderSnapshot(
        id=str(row.id),
        name=str(row.name),
        provider_type=str(row.provider_type),
        credentials=dict(row.credentials_json or {}),
        endpoint=(str(row.endpoint) if row.endpoint else None),
        extra=dict(row.extra_json or {}),
    )

