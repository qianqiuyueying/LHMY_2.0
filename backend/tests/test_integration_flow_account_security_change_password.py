"""集成测试：FLOW-ACCOUNT-SECURITY（改密）。

规格依据（单一真相来源）：
- specs-prod/admin/tasks.md#FLOW-ACCOUNT-SECURITY
- specs-prod/admin/api-contracts.md#2.6 / #2A.3 / #2B.2
"""

from __future__ import annotations

import asyncio
import os
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


async def _seed_admin(*, username: str, password: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Admin(
                id=str(uuid4()),
                username=username,
                password_hash=hash_password(password=password),
                status="ACTIVE",
                phone=None,
            )
        )
        await session.commit()


async def _seed_provider(*, username: str, password: str) -> None:
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


async def _seed_dealer(*, username: str, password: str) -> None:
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
                created_at=None,
                updated_at=None,
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


def test_flow_account_security_admin_change_password_policy_and_audit():
    asyncio.run(_reset_db_and_redis())
    # 满足 admin 密码策略：≥10 且至少 2 类
    asyncio.run(_seed_admin(username="it_admin", password="Abcdef!2345"))

    client = TestClient(app)
    r_login = client.post("/api/v1/admin/auth/login", json={"username": "it_admin", "password": "Abcdef!2345"})
    assert r_login.status_code == 200
    _assert_ok_envelope(r_login.json())
    token = r_login.json()["data"]["token"]

    # 新密码过短 -> 400 INVALID_ARGUMENT（策略）
    r_short = client.post(
        "/api/v1/admin/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"oldPassword": "Abcdef!2345", "newPassword": "short"},
    )
    assert r_short.status_code == 400
    _assert_fail_envelope(r_short.json(), code="INVALID_ARGUMENT")

    # 成功改密
    r_ok = client.post(
        "/api/v1/admin/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"oldPassword": "Abcdef!2345", "newPassword": "XyZ!2345678"},
    )
    assert r_ok.status_code == 200
    _assert_ok_envelope(r_ok.json())

    async def _assert_audit_written() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            row = (
                await session.scalars(
                    select(AuditLog)
                    .where(AuditLog.resource_type == "ADMIN_AUTH")
                    .where(AuditLog.summary.like("%修改密码%"))
                    .order_by(AuditLog.created_at.desc())
                    .limit(1)
                )
            ).first()
            assert row is not None

    asyncio.run(_assert_audit_written())


def test_flow_account_security_provider_and_dealer_change_password_min8_and_audit():
    asyncio.run(_reset_db_and_redis())
    asyncio.run(_seed_provider(username="it_provider", password="p@ssw0rd!"))
    asyncio.run(_seed_dealer(username="it_dealer", password="p@ssw0rd!"))

    client = TestClient(app)

    # provider：登录拿 token
    rp_login = client.post("/api/v1/provider/auth/login", json={"username": "it_provider", "password": "p@ssw0rd!"})
    assert rp_login.status_code == 200
    _assert_ok_envelope(rp_login.json())
    tp = rp_login.json()["data"]["token"]

    # provider：新密码 < 8 -> 400
    rp_short = client.post(
        "/api/v1/provider/auth/change-password",
        headers={"Authorization": f"Bearer {tp}"},
        json={"oldPassword": "p@ssw0rd!", "newPassword": "short"},
    )
    assert rp_short.status_code == 400
    _assert_fail_envelope(rp_short.json(), code="INVALID_ARGUMENT")

    # provider：成功改密
    rp_ok = client.post(
        "/api/v1/provider/auth/change-password",
        headers={"Authorization": f"Bearer {tp}"},
        json={"oldPassword": "p@ssw0rd!", "newPassword": "newpass88"},
    )
    assert rp_ok.status_code == 200
    _assert_ok_envelope(rp_ok.json())

    # dealer：登录拿 token
    rd_login = client.post("/api/v1/dealer/auth/login", json={"username": "it_dealer", "password": "p@ssw0rd!"})
    assert rd_login.status_code == 200
    _assert_ok_envelope(rd_login.json())
    td = rd_login.json()["data"]["token"]

    # dealer：旧密码错 -> 400
    rd_old_wrong = client.post(
        "/api/v1/dealer/auth/change-password",
        headers={"Authorization": f"Bearer {td}"},
        json={"oldPassword": "wrong", "newPassword": "newpass88"},
    )
    assert rd_old_wrong.status_code == 400
    _assert_fail_envelope(rd_old_wrong.json(), code="INVALID_ARGUMENT")

    # dealer：成功改密
    rd_ok = client.post(
        "/api/v1/dealer/auth/change-password",
        headers={"Authorization": f"Bearer {td}"},
        json={"oldPassword": "p@ssw0rd!", "newPassword": "newpass88"},
    )
    assert rd_ok.status_code == 200
    _assert_ok_envelope(rd_ok.json())

    async def _assert_audit_written() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            p = int(
                (
                    await session.execute(
                        select(AuditLog).where(AuditLog.resource_type == "PROVIDER_AUTH")  # noqa: WPS432
                    )
                )
                .scalars()
                .all()
                .__len__()
            )
            d = int(
                (
                    await session.execute(
                        select(AuditLog).where(AuditLog.resource_type == "DEALER_AUTH")  # noqa: WPS432
                    )
                )
                .scalars()
                .all()
                .__len__()
            )
            assert p >= 1
            assert d >= 1

    asyncio.run(_assert_audit_written())


