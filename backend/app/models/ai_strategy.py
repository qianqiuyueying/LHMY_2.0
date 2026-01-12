"""AI Strategy（业务语义层，v2）。

规格来源：
- specs/health-services-platform/ai-gateway-v2.md -> Provider/Strategy/Gateway

说明：
- Strategy 描述 AI “是干嘛的、怎么说话、有什么边界”，必须 Provider 无关。
- 绑定关系：Strategy 通过 provider_id 指向当前生效 Provider（可切换）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CommonEnabledStatus
from app.utils.datetime_utc import utcnow


class AiStrategy(Base):
    __tablename__ = "ai_strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Strategy ID")

    # 小程序侧/业务侧唯一标识：scene
    scene: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="场景（scene，唯一）")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="展示名称")

    # 绑定的 Provider（可切换）；不要求一定绑定（未绑定时 chat 需返回明确错误）
    provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True, comment="绑定的 Provider ID（可切换）")

    # 业务提示词模板（可为空字符串；DashScope 应用模式可能由应用内部控制）
    prompt_template: Mapped[str] = mapped_column(Text(), nullable=False, default="", comment="提示词模板（业务语义）")

    # generation_config 为建议值，Provider 不支持时允许忽略
    generation_config_json: Mapped[dict] = mapped_column(
        "generation_config",
        JSON,
        nullable=False,
        default=dict,
        comment="生成建议配置（JSON，provider 可降级忽略）",
    )

    # constraints：业务边界（例如 forbid_medical_diagnosis/safe_mode）
    constraints_json: Mapped[dict] = mapped_column(
        "constraints",
        JSON,
        nullable=False,
        default=dict,
        comment="业务约束（JSON）",
    )

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

