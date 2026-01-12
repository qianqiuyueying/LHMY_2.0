"""AI Provider（技术配置层，v2）。

规格来源：
- specs/health-services-platform/ai-gateway-v2.md -> Provider/Strategy/Gateway

说明：
- Provider 用于承载“能不能连上 AI”的技术配置（credentials/endpoint/extra）。
- credentials 的 schema 由对应 adapter 自行解释（后端/前端不做 provider 私有字段耦合）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CommonEnabledStatus
from app.utils.datetime_utc import utcnow


class AiProvider(Base):
    __tablename__ = "ai_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Provider ID")

    # 管理侧可读标识（用于绑定/切换）：例如 dashscope_app_prod
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="Provider 标识（唯一）")

    # provider 类型（枚举字符串）：dashscope_application/dashscope_model/openapi_compatible/custom_provider
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="Provider 类型")

    # 凭证（敏感）：禁止在 Admin 响应/审计中返回明文
    credentials_json: Mapped[dict] = mapped_column(
        "credentials",
        JSON,
        nullable=False,
        default=dict,
        comment="凭证（JSON，禁止返回明文）",
    )

    # 可选 endpoint（例如 OpenAPI baseUrl）
    endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="Endpoint（可选）")

    # 额外扩展字段（例如 default_model、timeoutMs、retries、rateLimitPerMinute）
    extra_json: Mapped[dict] = mapped_column("extra", JSON, nullable=False, default=dict, comment="扩展字段（JSON）")

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CommonEnabledStatus.ENABLED.value,
        comment="状态：ENABLED/DISABLED",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )

