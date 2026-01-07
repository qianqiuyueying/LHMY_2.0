"""集成测试：手机号唯一性（Admin 2FA / Provider&Dealer 注册）。

规格来源：
- specs-prod/admin/api-contracts.md
  - 2.7：admins.phone 全局唯一
  - 2A.1B：provider_users.phone 角色内唯一（跨角色允许重复）
  - 2B.1B：dealer_users.phone 角色内唯一（跨角色允许重复）

说明：
- 项目开发阶段允许清库：每个测试先清空 DB/Redis。
"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.admin import Admin
from app.models.base import Base
from app.models.dealer_user import DealerUser
from app.models.provider_user import ProviderUser
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


async def _set_sms_code(*, scene: str, phone: str, code: str = "123456") -> None:
    r = get_redis()
    await r.set(f"sms:code:{scene}:{phone}", code, ex=5 * 60)


def test_admin_phone_bind_phone_global_unique():
    asyncio.run(_reset_db_and_redis())

    admin1_id = "00000000-0000-0000-0000-00000000a101"
    admin2_id = "00000000-0000-0000-0000-00000000a102"
    admin1_token, _ = create_admin_token(admin_id=admin1_id)
    admin2_token, _ = create_admin_token(admin_id=admin2_id)

    async def _seed_admins() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin1_id,
                    username="it_admin_1",
                    password_hash=hash_password(password="Abcdef!2345"),
                    status="ACTIVE",
                    phone=None,
                )
            )
            session.add(
                Admin(
                    id=admin2_id,
                    username="it_admin_2",
                    password_hash=hash_password(password="Abcdef!2345"),
                    status="ACTIVE",
                    phone=None,
                )
            )
            await session.commit()

    asyncio.run(_seed_admins())

    phone = "13800138000"
    client = TestClient(app)

    # admin1 bind success
    asyncio.run(_set_sms_code(scene="ADMIN_BIND_PHONE", phone=phone, code="123456"))
    r = client.post(
        "/api/v1/admin/auth/phone-bind/verify",
        headers={"Authorization": f"Bearer {admin1_token}"},
        json={"phone": phone, "smsCode": "123456"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["ok"] is True

    # admin2 bind same phone -> 409 ALREADY_EXISTS
    asyncio.run(_set_sms_code(scene="ADMIN_BIND_PHONE", phone=phone, code="123456"))
    r = client.post(
        "/api/v1/admin/auth/phone-bind/verify",
        headers={"Authorization": f"Bearer {admin2_token}"},
        json={"phone": phone, "smsCode": "123456"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ALREADY_EXISTS"


def test_dealer_register_phone_unique_within_role():
    asyncio.run(_reset_db_and_redis())

    phone = "13800138001"
    client = TestClient(app)

    asyncio.run(_set_sms_code(scene="DEALER_REGISTER", phone=phone, code="123456"))
    r = client.post(
        "/api/v1/dealer/auth/register",
        json={
            "username": "it_dealer_reg_1",
            "password": "p@ssw0rd",
            "dealerName": "IT Dealer",
            "phone": phone,
            "smsCode": "123456",
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["submitted"] is True

    # same phone, different username -> 409 ALREADY_EXISTS
    asyncio.run(_set_sms_code(scene="DEALER_REGISTER", phone=phone, code="123456"))
    r = client.post(
        "/api/v1/dealer/auth/register",
        json={
            "username": "it_dealer_reg_2",
            "password": "p@ssw0rd",
            "dealerName": "IT Dealer 2",
            "phone": phone,
            "smsCode": "123456",
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ALREADY_EXISTS"

    async def _assert_phone_persisted() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            du = (await session.scalars(select(DealerUser).where(DealerUser.username == "it_dealer_reg_1").limit(1))).first()
            assert du is not None
            assert du.phone == phone

    # local import to avoid unused for sync-only tests
    from sqlalchemy import select  # noqa: WPS433

    asyncio.run(_assert_phone_persisted())


def test_provider_register_phone_unique_within_role_and_cross_role_allowed():
    asyncio.run(_reset_db_and_redis())

    phone = "13800138002"
    client = TestClient(app)

    # dealer registers with phone
    asyncio.run(_set_sms_code(scene="DEALER_REGISTER", phone=phone, code="123456"))
    r = client.post(
        "/api/v1/dealer/auth/register",
        json={
            "username": "it_dealer_reg_x",
            "password": "p@ssw0rd",
            "dealerName": "IT Dealer X",
            "phone": phone,
            "smsCode": "123456",
        },
    )
    assert r.status_code == 200

    # provider registers with same phone -> allowed (cross-role)
    asyncio.run(_set_sms_code(scene="PROVIDER_REGISTER", phone=phone, code="123456"))
    r = client.post(
        "/api/v1/provider/auth/register",
        json={
            "username": "it_provider_reg_1",
            "password": "p@ssw0rd",
            "providerName": "IT Provider",
            "phone": phone,
            "smsCode": "123456",
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["submitted"] is True

    async def _assert_phone_persisted() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            pu = (
                await session.scalars(select(ProviderUser).where(ProviderUser.username == "it_provider_reg_1").limit(1))
            ).first()
            assert pu is not None
            assert pu.phone == phone

    from sqlalchemy import select  # noqa: WPS433

    asyncio.run(_assert_phone_persisted())


