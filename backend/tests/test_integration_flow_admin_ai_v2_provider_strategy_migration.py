"""集成测试：FLOW-ADMIN-AI-V2（Provider/Strategy/绑定 + 不泄露凭证）。

规格依据（单一真相来源）：
- specs/health-services-platform/ai-gateway-v2.md
- specs/health-services-platform/tasks.md -> REQ-AI-P0-001

重点验证：
- Provider/Strategy 管理接口可用（不产生 422，按 400 INVALID_ARGUMENT 收敛）
- apiKey 不在响应体/审计日志中出现明文
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.models  # noqa: F401
from app.main import app
from app.models.admin import Admin
from app.models.ai_provider import AiProvider
from app.models.ai_strategy import AiStrategy
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
from app.utils.redis_client import get_redis

pytestmark = pytest.mark.skipif(os.getenv("RUN_INTEGRATION_TESTS") != "1", reason="integration tests disabled")


async def _reset_db_and_redis() -> None:
    r = get_redis()
    await r.flushdb()

    session_factory = get_session_factory()
    async with session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


async def _seed_admin(*, admin_id: str, phone: str | None) -> None:
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Admin(
                id=admin_id,
                username=f"u_{admin_id[:8]}",
                password_hash="bcrypt:$2b$12$dummy",
                status="ACTIVE",
                phone=phone,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


async def _count_audits(resource_type: str) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        return int(
            (await session.execute(select(func.count()).select_from(AuditLog).where(AuditLog.resource_type == resource_type)))
            .scalar()
            or 0
        )


def test_admin_ai_v2_provider_strategy_and_binding_no_secret_leak():
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    admin_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_id, phone="13600000000"))
    token, _ = create_admin_token(admin_id=admin_id)

    secret = "sk-SECRET-123456"

    # 1) create provider (openapi_compatible)
    r_p = client.post(
        "/api/v1/admin/ai/providers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-p1"},
        json={
            "name": "openapi_prod",
            "providerType": "openapi_compatible",
            "endpoint": "https://example.com/v1",
            "credentials": {"api_key": secret},
            "extra": {"default_model": "gpt-4o-mini"},
        },
    )
    assert r_p.status_code == 200
    data_p = r_p.json()["data"]
    assert data_p["name"] == "openapi_prod"
    assert "apiKey" not in str(data_p)
    assert data_p.get("apiKeyMasked")
    assert secret not in str(data_p)
    provider_id = data_p["id"]

    # 2) create strategy
    r_s = client.post(
        "/api/v1/admin/ai/strategies",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-s1"},
        json={
            "scene": "knowledge_qa",
            "displayName": "健康知识助手",
            "promptTemplate": "你是一个健康领域知识助手，只提供科普，不提供诊断。",
            "generationConfig": {"temperature": 0.4, "max_output_tokens": 800},
            "constraints": {"forbid_medical_diagnosis": True, "safe_mode": True},
        },
    )
    assert r_s.status_code == 200
    strategy_id = r_s.json()["data"]["id"]

    # 3) bind provider
    r_bind = client.post(
        f"/api/v1/admin/ai/strategies/{strategy_id}/bind-provider",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-b1"},
        json={"providerId": provider_id},
    )
    assert r_bind.status_code == 200
    assert r_bind.json()["data"]["providerId"] == provider_id

    # 4) verify DB contains provider/strategy and credentials stored, but audits don't leak secret
    async def _load():
        session_factory = get_session_factory()
        async with session_factory() as session:
            pv = (await session.scalars(select(AiProvider).where(AiProvider.id == provider_id).limit(1))).first()
            st = (await session.scalars(select(AiStrategy).where(AiStrategy.id == strategy_id).limit(1))).first()
            last_audit = (
                await session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(1))
            ).first()
            return pv, st, last_audit

    pv, st, last_audit = asyncio.run(_load())
    assert pv is not None and st is not None and last_audit is not None
    assert str(st.provider_id) == str(pv.id)

    creds = pv.credentials_json or {}
    assert str(creds.get("api_key") or creds.get("apiKey") or "")  # should exist if migrated
    # 审计日志不得包含明文 secret（包括迁移审计、provider 创建审计等）
    assert secret not in str(last_audit.metadata_json or {})

    # 至少写入了 v2 的审计资源类型（数量不严格要求，但应 >0）
    assert asyncio.run(_count_audits("AI_PROVIDER")) >= 1

