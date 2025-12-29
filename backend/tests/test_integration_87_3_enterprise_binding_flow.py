"""端到端集成测试：职健行动企业绑定流程（阶段17-87.3）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段17-87.3
- specs/health-services-platform/design.md -> 企业绑定（v1 必须人工审核，PENDING->APPROVED 后获得 EMPLOYEE）
- specs/health-services-platform/design.md -> `POST /api/v1/auth/bind-enterprise`
- specs/health-services-platform/design.md -> `PUT /api/v1/admin/enterprise-bindings/{id}/approve`
- specs/health-services-platform/design.md -> `GET /api/v1/users/profile`

测试目标（v1 最小）：
- USER 提交企业绑定 -> PENDING
- ADMIN 审核通过 -> APPROVED + users.enterprise 写入 + EMPLOYEE 身份生效
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
from app.models.base import Base
from app.models.user import User
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
from app.utils.jwt_token import create_user_token
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


def test_stage17_87_3_enterprise_binding_flow():
    asyncio.run(_reset_db_and_redis())

    user_id = str(uuid4())
    admin_id = str(uuid4())

    async def _seed_user() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                User(
                    id=user_id, phone="13700000000", openid=None, unionid=None, nickname="u", avatar=None, identities=[]
                )
            )
            await session.commit()

    asyncio.run(_seed_user())

    client = TestClient(app)
    user_token = create_user_token(user_id=user_id, channel="MINI_PROGRAM")
    admin_token, _jti = create_admin_token(admin_id=admin_id)

    # 1) USER 提交绑定
    r1 = client.post(
        "/api/v1/auth/bind-enterprise",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"enterpriseName": "测试企业A", "cityCode": "CITY:110100"},
    )
    assert r1.status_code == 200
    binding_id = r1.json()["data"]["bindingId"]
    assert r1.json()["data"]["status"] == "PENDING"

    # 2) ADMIN 审核通过
    r2 = client.put(
        f"/api/v1/admin/enterprise-bindings/{binding_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "APPROVED"

    # 3) USER 获取 profile：应具备 EMPLOYEE 身份与 enterprise 字段
    r3 = client.get("/api/v1/users/profile", headers={"Authorization": f"Bearer {user_token}"})
    assert r3.status_code == 200
    profile = r3.json()["data"]
    assert profile["id"] == user_id
    assert "EMPLOYEE" in profile["identities"]
    assert profile["enterpriseId"]
    assert profile["enterpriseName"] == "测试企业A"
