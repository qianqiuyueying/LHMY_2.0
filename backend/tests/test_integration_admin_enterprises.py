"""集成测试：Admin 企业库查询（BE-ADMIN-006，v1 只读部分）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-006

说明：
- 需要 MySQL/Redis，因此仅在 RUN_INTEGRATION_TESTS=1 时运行。
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.enterprise import Enterprise
from app.models.enums import EnterpriseSource
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


def test_admin_enterprises_list_and_detail():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    token, _jti = create_admin_token(admin_id=admin_id)

    eid = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Enterprise(
                    id=eid,
                    name="测试企业X",
                    country_code="COUNTRY:CN",
                    province_code="PROVINCE:110000",
                    city_code="CITY:110100",
                    source=EnterpriseSource.USER_FIRST_BINDING.value,
                    first_seen_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)

    r1 = client.get(
        "/api/v1/admin/enterprises?keyword=%E6%B5%8B%E8%AF%95",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["data"]["total"] == 1

    r2 = client.get(f"/api/v1/admin/enterprises/{eid}", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["data"]["id"] == eid
    assert r2.json()["data"]["cityCode"] == "CITY:110100"


def test_admin_enterprises_put_update_name_only():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    token, _jti = create_admin_token(admin_id=admin_id)

    eid = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Enterprise(
                    id=eid,
                    name="旧企业名",
                    country_code="COUNTRY:CN",
                    province_code="PROVINCE:110000",
                    city_code="CITY:110100",
                    source=EnterpriseSource.USER_FIRST_BINDING.value,
                    first_seen_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)

    # 允许更新 name（并自动 strip）
    r1 = client.put(
        f"/api/v1/admin/enterprises/{eid}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": " 新企业名 "},
    )
    assert r1.status_code == 200
    assert r1.json()["data"]["id"] == eid
    assert r1.json()["data"]["name"] == "新企业名"

    # 禁止更新其它字段（extra=forbid -> INVALID_ARGUMENT 400）
    r2 = client.put(
        f"/api/v1/admin/enterprises/{eid}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "新企业名2", "cityCode": "CITY:310100"},
    )
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "INVALID_ARGUMENT"
