"""集成测试：Admin 用户查询（BE-ADMIN-007）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-007

说明：
- 需要 MySQL/Redis，因此仅在 RUN_INTEGRATION_TESTS=1 时运行。
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.user import User
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


def test_admin_users_list_and_detail():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    token, _jti = create_admin_token(admin_id=admin_id)

    uid = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                User(
                    id=uid,
                    phone="13800000000",
                    openid=None,
                    unionid=None,
                    nickname="nick",
                    avatar=None,
                    identities=["MEMBER"],
                    enterprise_id=None,
                    enterprise_name=None,
                    binding_time=None,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)

    r1 = client.get(
        "/api/v1/admin/users?identity=MEMBER",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["data"]["total"] == 1
    item = r1.json()["data"]["items"][0]
    assert item["id"] == uid
    assert item["phoneMasked"] == "138****0000"
    assert "phone" not in item

    r2 = client.get(f"/api/v1/admin/users/{uid}", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["data"]["id"] == uid
    assert r2.json()["data"]["phoneMasked"] == "138****0000"
    assert "phone" not in r2.json()["data"]

    # identity 非法 -> 400 INVALID_ARGUMENT
    r3 = client.get("/api/v1/admin/users?identity=BAD", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 400
    assert r3.json()["success"] is False
    assert r3.json()["error"]["code"] == "INVALID_ARGUMENT"

    # 用户不存在 -> 404 NOT_FOUND
    r4 = client.get(f"/api/v1/admin/users/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert r4.status_code == 404
    assert r4.json()["success"] is False
    assert r4.json()["error"]["code"] == "NOT_FOUND"
