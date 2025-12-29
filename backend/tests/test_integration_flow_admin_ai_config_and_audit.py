"""集成测试：FLOW-ADMIN-AI（配置门禁/幂等/审计/错误码收敛）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9P
  - PUT /admin/ai/config：必须 require_admin_phone_bound；强制 Idempotency-Key；字段校验失败收敛 400 INVALID_ARGUMENT（不走 422）
  - 仅当“实际变更”时 bump version + 写审计；审计 metadata 禁止存 apiKey 明文；幂等复放不重复写审计
- specs-prod/admin/tasks.md#FLOW-ADMIN-AI
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


async def _count_ai_config_audits() -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        return int(
            (await session.execute(select(func.count()).select_from(AuditLog).where(AuditLog.resource_type == "AI_CONFIG")))
            .scalar()
            or 0
        )


def test_admin_ai_config_put_requires_phone_bound_and_idempotency_and_no_422_and_audit_once():
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    # 1) phone 未绑定：403 ADMIN_PHONE_REQUIRED
    admin_id_unbound = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_id_unbound, phone=None))
    token_unbound, _ = create_admin_token(admin_id=admin_id_unbound)
    r_unbound = client.put(
        "/api/v1/admin/ai/config",
        headers={"Authorization": f"Bearer {token_unbound}", "Idempotency-Key": "k1"},
        json={"enabled": True},
    )
    assert r_unbound.status_code == 403
    assert r_unbound.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # 2) phone 已绑定：缺少 Idempotency-Key -> 400 INVALID_ARGUMENT（而不是 422）
    admin_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_id, phone="13600000000"))
    token, _ = create_admin_token(admin_id=admin_id)

    r_missing_key = client.put(
        "/api/v1/admin/ai/config",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": True},
    )
    assert r_missing_key.status_code == 400
    assert r_missing_key.json()["error"]["code"] == "INVALID_ARGUMENT"

    # 3) 字段范围非法：必须 400 INVALID_ARGUMENT（不走 FastAPI 422）
    r_bad = client.put(
        "/api/v1/admin/ai/config",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-bad"},
        json={"temperature": 3},
    )
    assert r_bad.status_code == 400
    assert r_bad.json()["error"]["code"] == "INVALID_ARGUMENT"

    # 4) no-op：不 bump version、不写审计；但仍可缓存幂等结果
    r_get1 = client.get("/api/v1/admin/ai/config", headers={"Authorization": f"Bearer {token}"})
    assert r_get1.status_code == 200
    v1 = r_get1.json()["data"]["version"]

    r_noop = client.put(
        "/api/v1/admin/ai/config",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-noop"},
        json={"provider": "OPENAI_COMPAT"},
    )
    assert r_noop.status_code == 200
    assert "apiKey" not in r_noop.json()["data"]
    assert r_noop.json()["data"]["version"] == v1
    assert asyncio.run(_count_ai_config_audits()) == 0

    # 5) 实际变更：bump version + 写审计一次；重放不重复写审计；审计不含 apiKey 明文
    secret = "sk-SECRET-123456"
    r_change1 = client.put(
        "/api/v1/admin/ai/config",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-change-1"},
        json={"baseUrl": "https://example.com", "model": "gpt-4.1-mini", "apiKey": secret},
    )
    assert r_change1.status_code == 200
    v2 = r_change1.json()["data"]["version"]
    assert v2 != v1
    assert "apiKey" not in r_change1.json()["data"]

    assert asyncio.run(_count_ai_config_audits()) == 1

    # 重放：同 key -> 200，且审计仍为 1
    r_change_replay = client.put(
        "/api/v1/admin/ai/config",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-change-1"},
        json={"baseUrl": "https://example.com", "model": "gpt-4.1-mini", "apiKey": secret},
    )
    assert r_change_replay.status_code == 200
    assert r_change_replay.json()["data"]["version"] == v2
    assert asyncio.run(_count_ai_config_audits()) == 1

    # 审计 metadata 不得包含 apiKey 明文
    session_factory = get_session_factory()
    async def _load_audit_meta() -> dict:
        async with session_factory() as session:
            row = (
                await session.scalars(
                    select(AuditLog).where(AuditLog.resource_type == "AI_CONFIG").order_by(AuditLog.created_at.desc()).limit(1)
                )
            ).first()
            assert row is not None
            return row.metadata_json or {}

    meta = asyncio.run(_load_audit_meta())
    assert secret not in str(meta)
    assert meta.get("apiKeyUpdated") is True


