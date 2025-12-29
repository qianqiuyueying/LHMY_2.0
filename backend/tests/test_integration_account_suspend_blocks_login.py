"""集成测试：冻结账号后禁止登录（v1 最小）。

规格来源：
- specs/功能实现/admin/tasks.md -> T-N12

目标：
- ProviderUser/DealerUser 被置为 SUSPENDED 后：
  - 登录被拒绝（401/403，且为稳定错误码）
  - 不影响历史数据（本用例不覆盖历史查询，只覆盖“禁止登录”）
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# 本地/Windows 直接跑集成测试时，通常是宿主机连接 docker 暴露端口；
# 若未显式设置，则默认走 localhost，避免解析 docker service name 失败。
os.environ.setdefault("MYSQL_HOST", "127.0.0.1")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("REDIS_HOST", "127.0.0.1")
os.environ.setdefault("REDIS_PORT", "6379")

import app.models  # noqa: F401
from app.main import app
from app.models.admin import Admin
from app.models.base import Base
from app.models.user import User
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


def test_suspend_provider_user_blocks_provider_login():
    asyncio.run(_reset_db_and_redis())

    client = TestClient(app)
    admin_id = str(uuid4())
    admin_token, _ = create_admin_token(admin_id=admin_id)

    # FLOW-ACCOUNTS 高风险门禁：写操作要求 admin 绑定手机号
    async def _seed_admin_phone_bound() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin_id,
                    username="it_admin_suspend_1",
                    password_hash=hash_password(password="Abcdef!2345"),
                    status="ACTIVE",
                    phone="13800138000",
                )
            )
            await session.commit()

    # 0) seed 一个普通 user（避免某些测试环境依赖 users 表为空时异常；并非本用例重点）
    async def _seed_user() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(User(id=str(uuid4()), phone="13900000000", nickname="u", identities=[]))
            await session.commit()

    asyncio.run(_seed_admin_phone_bound())
    asyncio.run(_seed_user())

    # 1) ADMIN 创建 ProviderUser
    r1 = client.post(
        "/api/v1/admin/provider-users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "p_u1", "providerName": "P1"},
    )
    assert r1.status_code == 200
    password = r1.json()["data"]["password"]
    provider_user_id = r1.json()["data"]["providerUser"]["id"]

    # 2) Provider 登录成功
    r2 = client.post("/api/v1/provider/auth/login", json={"username": "p_u1", "password": password})
    assert r2.status_code == 200

    # 3) 冻结 ProviderUser
    r3 = client.post(
        f"/api/v1/admin/provider-users/{provider_user_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r3.status_code == 200

    # 4) 再次登录应失败
    r4 = client.post("/api/v1/provider/auth/login", json={"username": "p_u1", "password": password})
    assert r4.status_code in (401, 403)


def test_suspend_dealer_user_blocks_dealer_login():
    asyncio.run(_reset_db_and_redis())

    client = TestClient(app)
    admin_id = str(uuid4())
    admin_token, _ = create_admin_token(admin_id=admin_id)

    async def _seed_admin_phone_bound() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin_id,
                    username="it_admin_suspend_2",
                    password_hash=hash_password(password="Abcdef!2345"),
                    status="ACTIVE",
                    phone="13800138000",
                )
            )
            await session.commit()

    asyncio.run(_seed_admin_phone_bound())

    # 1) ADMIN 创建 DealerUser
    r1 = client.post(
        "/api/v1/admin/dealer-users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "d_u1", "dealerName": "D1"},
    )
    assert r1.status_code == 200
    password = r1.json()["data"]["password"]
    dealer_user_id = r1.json()["data"]["dealerUser"]["id"]

    # 2) Dealer 登录成功
    r2 = client.post("/api/v1/dealer/auth/login", json={"username": "d_u1", "password": password})
    assert r2.status_code == 200

    # 3) 冻结 DealerUser
    r3 = client.post(
        f"/api/v1/admin/dealer-users/{dealer_user_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r3.status_code == 200

    # 4) 再次登录应失败
    r4 = client.post("/api/v1/dealer/auth/login", json={"username": "d_u1", "password": password})
    assert r4.status_code in (401, 403)

