"""集成测试：FLOW-AUTH-LOGIN / FLOW-AUTH-REFRESH（最小护栏）。

规格依据（单一真相来源）：
- specs-prod/admin/tasks.md#FLOW-AUTH-LOGIN
- specs-prod/admin/tasks.md#FLOW-AUTH-REFRESH
- specs-prod/admin/api-contracts.md#2 Admin Auth
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
from app.models.dealer import Dealer
from app.models.dealer_user import DealerUser
from app.models.enums import DealerStatus
from app.models.provider import Provider
from app.models.provider_user import ProviderUser
from app.services.password_hashing import hash_password
from app.utils.db import get_session_factory
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
    assert isinstance(resp_json.get("requestId"), str) and resp_json["requestId"]


def _assert_ok_envelope(resp_json: dict) -> None:
    assert resp_json["success"] is True
    assert "data" in resp_json
    assert isinstance(resp_json.get("requestId"), str) and resp_json["requestId"]


async def _seed_admin(*, username: str, password: str, phone: str | None = None) -> str:
    admin_id = str(uuid4())
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Admin(
                id=admin_id,
                username=username,
                password_hash=hash_password(password=password),
                status="ACTIVE",
                phone=phone,
            )
        )
        await session.commit()
    return admin_id


async def _seed_provider_user(*, username: str, password: str) -> None:
    provider_id = str(uuid4())
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(Provider(id=provider_id, name="IT Provider"))
        session.add(
            ProviderUser(
                id=str(uuid4()),
                provider_id=provider_id,
                username=username,
                password_hash=hash_password(password=password),
                status="ACTIVE",
            )
        )
        await session.commit()


async def _seed_dealer_user(*, username: str, password: str) -> None:
    dealer_id = str(uuid4())
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Dealer(
                id=dealer_id,
                name="IT Dealer",
                level=None,
                parent_dealer_id=None,
                status=DealerStatus.ACTIVE.value,
                contact_name=None,
                contact_phone=None,
                created_at=datetime.now(tz=UTC).replace(tzinfo=None),
                updated_at=datetime.now(tz=UTC).replace(tzinfo=None),
            )
        )
        session.add(
            DealerUser(
                id=str(uuid4()),
                dealer_id=dealer_id,
                username=username,
                password_hash=hash_password(password=password),
                status="ACTIVE",
            )
        )
        await session.commit()


def test_flow_auth_login_admin_wrong_password_401_code_and_envelope():
    asyncio.run(_reset_db_and_redis())
    asyncio.run(_seed_admin(username="it_admin", password="Abcdef!2345"))

    client = TestClient(app)
    r = client.post("/api/v1/admin/auth/login", json={"username": "it_admin", "password": "wrong"})
    assert r.status_code == 401
    _assert_fail_envelope(r.json(), code="ADMIN_CREDENTIALS_INVALID")


def test_flow_auth_login_provider_and_dealer_success_write_audit_login():
    asyncio.run(_reset_db_and_redis())
    asyncio.run(_seed_provider_user(username="it_provider", password="p@ssw0rd!"))
    asyncio.run(_seed_dealer_user(username="it_dealer", password="p@ssw0rd!"))

    client = TestClient(app)

    rp = client.post("/api/v1/provider/auth/login", json={"username": "it_provider", "password": "p@ssw0rd!"})
    assert rp.status_code == 200
    _assert_ok_envelope(rp.json())
    assert rp.json()["data"]["actor"]["actorType"] in ("PROVIDER", "PROVIDER_STAFF")

    rd = client.post("/api/v1/dealer/auth/login", json={"username": "it_dealer", "password": "p@ssw0rd!"})
    assert rd.status_code == 200
    _assert_ok_envelope(rd.json())
    assert rd.json()["data"]["actor"]["actorType"] == "DEALER"

    async def _assert_audit_login_exists() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            n = int(
                (
                    await session.execute(
                        select(AuditLog).where(AuditLog.action == "LOGIN").limit(10)  # noqa: WPS432
                    )
                )
                .scalars()
                .all()
                .__len__()
            )
            assert n >= 2

    asyncio.run(_assert_audit_login_exists())


def test_flow_auth_refresh_admin_once_ok_twice_401_and_logout_blocks_token():
    asyncio.run(_reset_db_and_redis())
    asyncio.run(_seed_admin(username="it_admin", password="Abcdef!2345"))

    client = TestClient(app)
    r_login = client.post("/api/v1/admin/auth/login", json={"username": "it_admin", "password": "Abcdef!2345"})
    assert r_login.status_code == 200
    _assert_ok_envelope(r_login.json())
    token_a = r_login.json()["data"]["token"]

    r_refresh = client.post("/api/v1/admin/auth/refresh", headers={"Authorization": f"Bearer {token_a}"})
    assert r_refresh.status_code == 200
    _assert_ok_envelope(r_refresh.json())
    token_b = r_refresh.json()["data"]["token"]

    # 同一旧 token 二次 refresh：必须 401（blacklist 生效）
    r_refresh_again = client.post("/api/v1/admin/auth/refresh", headers={"Authorization": f"Bearer {token_a}"})
    assert r_refresh_again.status_code == 401
    _assert_fail_envelope(r_refresh_again.json(), code="UNAUTHENTICATED")

    # 新 token 可访问 admin API
    r_admin_ok = client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {token_b}"})
    assert r_admin_ok.status_code == 200
    _assert_ok_envelope(r_admin_ok.json())

    # logout 后 tokenB 失效
    r_logout = client.post("/api/v1/admin/auth/logout", headers={"Authorization": f"Bearer {token_b}"})
    assert r_logout.status_code == 200
    _assert_ok_envelope(r_logout.json())

    r_admin_after_logout = client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {token_b}"})
    assert r_admin_after_logout.status_code == 401
    _assert_fail_envelope(r_admin_after_logout.json(), code="UNAUTHENTICATED")


