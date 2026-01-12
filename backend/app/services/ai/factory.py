"""Provider Adapter Factory（v2）。"""

from __future__ import annotations

from fastapi import HTTPException

from app.models.enums import AiProviderType
from app.services.ai.adapters.base import ProviderAdapter
from app.services.ai.adapters.dashscope_application import DashScopeApplicationAdapter
from app.services.ai.adapters.dashscope_model import DashScopeModelAdapter
from app.services.ai.adapters.openai_compatible import OpenAiCompatibleAdapter
from app.services.ai.types import AiProviderSnapshot


def create_adapter(provider: AiProviderSnapshot) -> ProviderAdapter:
    t = str(provider.provider_type or "")
    if t == AiProviderType.OPENAPI_COMPATIBLE.value:
        return OpenAiCompatibleAdapter()
    if t == AiProviderType.DASHSCOPE_APPLICATION.value:
        return DashScopeApplicationAdapter()
    if t == AiProviderType.DASHSCOPE_MODEL.value:
        return DashScopeModelAdapter()

    # 预留：custom_provider 后续实现
    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "AI Provider 类型不支持"})

