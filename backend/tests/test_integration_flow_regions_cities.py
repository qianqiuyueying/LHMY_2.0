"""集成测试：FLOW-REGIONS-CITIES（城市配置发布/下线/导入：门禁 + 幂等 + 审计）。

规格依据（单一真相来源）：
- specs-prod/admin/tasks.md#FLOW-REGIONS-CITIES
- specs-prod/admin/security.md#1.4（高风险操作 phone bound）
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

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


async def _seed_admin(*, admin_id: str, phone: str | None) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Admin(
                id=admin_id,
                username=f"it_admin_regions_{admin_id[-4:]}",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone=phone,
            )
        )
        await session.commit()


async def _audit_count(*, action: str) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        n = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.resource_type == "REGION_CITIES")
                    .where(AuditLog.resource_id == "REGION_CITIES")
                    .where(AuditLog.action == action)
                )
            ).scalar()
            or 0
        )
        return n


def test_regions_cities_phone_bound_publish_offline_import_idempotent_and_audited():
    asyncio.run(_reset_db_and_redis())
    unbound_id = str(uuid4())
    bound_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=unbound_id, phone=None))
    asyncio.run(_seed_admin(admin_id=bound_id, phone="13800138000"))

    unbound_token, _ = create_admin_token(admin_id=unbound_id)
    bound_token, _ = create_admin_token(admin_id=bound_id)
    client = TestClient(app)

    # 准备：写入一条草稿（PUT 不要求 phone bound）
    r_put = client.put(
        "/api/v1/admin/regions/cities",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"items": [{"code": "CITY:110100", "name": "北京", "sort": 1, "enabled": True}]},
    )
    assert r_put.status_code == 200

    # 1) 未绑定手机号：publish/offline/import -> 403 ADMIN_PHONE_REQUIRED
    r1 = client.post("/api/v1/admin/regions/cities/publish", headers={"Authorization": f"Bearer {unbound_token}"})
    assert r1.status_code == 403
    assert r1.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    r2 = client.post("/api/v1/admin/regions/cities/offline", headers={"Authorization": f"Bearer {unbound_token}"})
    assert r2.status_code == 403
    assert r2.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    r3 = client.post("/api/v1/admin/regions/cities/import-cn", headers={"Authorization": f"Bearer {unbound_token}"})
    assert r3.status_code == 403
    assert r3.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # 2) publish：首次推进 version + 写审计；重复 publish no-op（version 不变、审计不重复）
    rp1 = client.post("/api/v1/admin/regions/cities/publish", headers={"Authorization": f"Bearer {bound_token}"})
    assert rp1.status_code == 200
    v_pub = str(rp1.json()["data"]["version"])
    assert v_pub and v_pub != "0"

    rp2 = client.post("/api/v1/admin/regions/cities/publish", headers={"Authorization": f"Bearer {bound_token}"})
    assert rp2.status_code == 200
    assert str(rp2.json()["data"]["version"]) == v_pub
    assert asyncio.run(_audit_count(action="PUBLISH")) == 1

    # 3) offline：首次推进 version + 写审计；重复 offline no-op
    ro1 = client.post("/api/v1/admin/regions/cities/offline", headers={"Authorization": f"Bearer {bound_token}"})
    assert ro1.status_code == 200
    v_off = str(ro1.json()["data"]["version"])
    assert v_off and v_off != "0"

    ro2 = client.post("/api/v1/admin/regions/cities/offline", headers={"Authorization": f"Bearer {bound_token}"})
    assert ro2.status_code == 200
    assert str(ro2.json()["data"]["version"]) == v_off
    assert asyncio.run(_audit_count(action="OFFLINE")) == 1

    # 4) import-cn：首次写审计；重复 import-cn（replace=true）若无变更则 no-op 不重复写审计
    ri1 = client.post("/api/v1/admin/regions/cities/import-cn", headers={"Authorization": f"Bearer {bound_token}"})
    assert ri1.status_code == 200
    assert ri1.json()["success"] is True
    assert isinstance(ri1.json()["data"]["items"], list)
    assert asyncio.run(_audit_count(action="UPDATE")) == 1

    ri2 = client.post("/api/v1/admin/regions/cities/import-cn", headers={"Authorization": f"Bearer {bound_token}"})
    assert ri2.status_code == 200
    assert asyncio.run(_audit_count(action="UPDATE")) == 1


