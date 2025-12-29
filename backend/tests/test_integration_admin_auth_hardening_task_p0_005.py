"""集成测试：管理员账号与会话安全加固（TASK-P0-005）。

规格依据（单一真相来源）：
- specs-prod/admin/security.md#1.4（seed/密码策略/锁定/2FA/绑定手机号）
- specs-prod/admin/api-contracts.md#2 Admin Auth
- specs-prod/admin/api-contracts.md#7 错误码与语义（429/403）
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.admin import Admin
from app.models.base import Base
from app.models.enums import SettlementStatus
from app.models.settlement_record import SettlementRecord
from app.services.password_hashing import hash_password
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
from app.utils.redis_client import get_redis
from app.utils.settings import settings

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
    assert resp_json.get("success") is False
    assert resp_json.get("data") is None
    assert resp_json.get("error", {}).get("code") == code
    assert isinstance(resp_json.get("error", {}).get("message"), str)
    assert isinstance(resp_json.get("requestId"), str)


def test_production_env_disables_admin_init_seed():
    """生产环境：即使配置 ADMIN_INIT_* 也不得在 login 请求路径内自动创建账号。"""
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    # patch settings at runtime
    old_env = settings.app_env
    old_u = settings.admin_init_username
    old_p = settings.admin_init_password
    settings.app_env = "production"
    settings.admin_init_username = "seed_admin"
    settings.admin_init_password = "AnyStrongPass#1"

    r = client.post("/api/v1/admin/auth/login", json={"username": "seed_admin", "password": "AnyStrongPass#1"})
    assert r.status_code == 401
    _assert_fail_envelope(r.json(), code="ADMIN_CREDENTIALS_INVALID")

    # cleanup
    settings.app_env = old_env
    settings.admin_init_username = old_u
    settings.admin_init_password = old_p


def test_admin_password_policy_enforced_on_change_password():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin_id,
                    username="it_admin_1",
                    password_hash=hash_password(password="OldPass#123"),
                    status="ACTIVE",
                    phone=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    token, _jti = create_admin_token(admin_id=admin_id)
    # too short and too weak
    r = client.post(
        "/api/v1/admin/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"oldPassword": "OldPass#123", "newPassword": "12345678"},
    )
    assert r.status_code == 400
    _assert_fail_envelope(r.json(), code="INVALID_ARGUMENT")


def test_admin_login_lockout_429_rate_limited_after_5_failures():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin_id,
                    username="lock_me",
                    password_hash=hash_password(password="RightPass#123"),
                    status="ACTIVE",
                    phone=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    # 5 次失败：返回 401
    for _ in range(5):
        r = client.post("/api/v1/admin/auth/login", json={"username": "lock_me", "password": "wrong"})
        assert r.status_code == 401
        _assert_fail_envelope(r.json(), code="ADMIN_CREDENTIALS_INVALID")

    # 第 6 次：锁定 -> 429 RATE_LIMITED
    r6 = client.post("/api/v1/admin/auth/login", json={"username": "lock_me", "password": "wrong"})
    assert r6.status_code == 429
    _assert_fail_envelope(r6.json(), code="RATE_LIMITED")


def test_high_risk_admin_op_requires_phone_bound():
    """高风险操作：未绑定手机号 -> 403 ADMIN_PHONE_REQUIRED。"""
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin_id,
                    username="no_phone_admin",
                    password_hash=hash_password(password="RightPass#123"),
                    status="ACTIVE",
                    phone=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                SettlementRecord(
                    id=str(uuid4()),
                    dealer_id=str(uuid4()),
                    cycle="2025-12",
                    order_count=0,
                    amount=0.0,
                    status=SettlementStatus.PENDING_CONFIRM.value,
                    created_at=now,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    token, _jti = create_admin_token(admin_id=admin_id)
    r = client.post(
        "/api/v1/admin/dealer-settlements/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"cycle": "2025-12"},
    )
    assert r.status_code == 403
    _assert_fail_envelope(r.json(), code="ADMIN_PHONE_REQUIRED")


