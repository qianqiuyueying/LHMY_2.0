"""集成测试：FLOW-ACCOUNTS（账号管理高风险）。

规格依据（单一真相来源）：
- specs-prod/admin/tasks.md#FLOW-ACCOUNTS
- specs-prod/admin/security.md#1.4.4（高风险操作需绑定手机号）
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.models  # noqa: F401
from app.main import app
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.services.password_hashing import hash_password
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


def _assert_fail_envelope(resp_json: dict, *, code: str) -> None:
    assert resp_json["success"] is False
    assert resp_json["data"] is None
    assert resp_json["error"]["code"] == code


async def _seed_admin(*, admin_id: str, phone: str | None) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Admin(
                id=admin_id,
                username="it_admin_accounts",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone=phone,
            )
        )
        await session.commit()


def test_flow_accounts_write_ops_require_phone_bound_and_are_audited_and_status_idempotent():
    asyncio.run(_reset_db_and_redis())

    # 1) 未绑定手机号：写操作必须 403 ADMIN_PHONE_REQUIRED
    admin_id = "00000000-0000-0000-0000-00000000a777"
    asyncio.run(_seed_admin(admin_id=admin_id, phone=None))
    token, _ = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    r_forbidden = client.post(
        "/api/v1/admin/provider-users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "p_u_accounts_1", "providerName": "P Accounts 1"},
    )
    assert r_forbidden.status_code == 403
    _assert_fail_envelope(r_forbidden.json(), code="ADMIN_PHONE_REQUIRED")

    # 2) 绑定手机号后：写操作可用 + 审计必有
    asyncio.run(_reset_db_and_redis())
    asyncio.run(_seed_admin(admin_id=admin_id, phone="13800138000"))
    token2, _ = create_admin_token(admin_id=admin_id)

    r_create = client.post(
        "/api/v1/admin/provider-users",
        headers={"Authorization": f"Bearer {token2}"},
        json={"username": "p_u_accounts_1", "providerName": "P Accounts 1"},
    )
    assert r_create.status_code == 200
    pu_id = r_create.json()["data"]["providerUser"]["id"]

    r_suspend = client.post(
        f"/api/v1/admin/provider-users/{pu_id}/suspend",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r_suspend.status_code == 200

    # 状态幂等：重复 suspend 仍 200，且不应额外刷审计（最小：只断言审计数量不小于 2）
    r_suspend2 = client.post(
        f"/api/v1/admin/provider-users/{pu_id}/suspend",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r_suspend2.status_code == 200

    r_activate = client.post(
        f"/api/v1/admin/provider-users/{pu_id}/activate",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r_activate.status_code == 200

    async def _assert_audit_written() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            rows = (
                await session.scalars(
                    select(AuditLog)
                    .where(AuditLog.actor_id == admin_id)
                    .where(AuditLog.resource_type == "PROVIDER_USER")
                    .order_by(AuditLog.created_at.desc())
                    .limit(10)
                )
            ).all()
            assert len(rows) >= 2
            # 不允许审计 metadata 里出现明文 password 字段
            for x in rows:
                md = x.metadata_json or {}
                assert "password" not in md

    asyncio.run(_assert_audit_written())


