"""集成测试：FLOW-PUBLISH-WEBSITE（官网配置发布：门禁 + 审计 + no-op）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#6（Admin Website Config：PUT require_admin_phone_bound + 审计 + no-op）
- specs-prod/admin/tasks.md#FLOW-PUBLISH-WEBSITE
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
                username=f"it_admin_website_{admin_id[-4:]}",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone=phone,
            )
        )
        await session.commit()


def test_publish_website_config_requires_phone_bound_and_writes_audit_and_noop():
    asyncio.run(_reset_db_and_redis())

    unbound_admin_id = str(uuid4())
    bound_admin_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=unbound_admin_id, phone=None))
    asyncio.run(_seed_admin(admin_id=bound_admin_id, phone="13800138000"))

    unbound_token, _ = create_admin_token(admin_id=unbound_admin_id)
    bound_token, _ = create_admin_token(admin_id=bound_admin_id)

    client = TestClient(app)

    # 1) 未绑定手机号 -> 403 ADMIN_PHONE_REQUIRED
    r1 = client.put(
        "/api/v1/admin/website/external-links",
        headers={"Authorization": f"Bearer {unbound_token}"},
        json={"miniProgramUrl": "https://example.com/mp", "h5BuyUrl": "https://example.com/h5"},
    )
    assert r1.status_code == 403
    assert r1.json()["success"] is False
    assert r1.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # 2) 绑定手机号 -> 200，写一次审计
    r2 = client.put(
        "/api/v1/admin/website/external-links",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"miniProgramUrl": "https://example.com/mp", "h5BuyUrl": "https://example.com/h5"},
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    v1 = str(r2.json()["data"]["version"])
    assert v1 and v1 != "0"

    # 3) 相同 body 再提交 -> 200 no-op，version 不变，审计不重复
    r3 = client.put(
        "/api/v1/admin/website/external-links",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"miniProgramUrl": "https://example.com/mp", "h5BuyUrl": "https://example.com/h5"},
    )
    assert r3.status_code == 200
    assert r3.json()["success"] is True
    assert str(r3.json()["data"]["version"]) == v1

    async def _assert_audit_once() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            n = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(AuditLog)
                        .where(AuditLog.resource_type == "WEBSITE_CONFIG")
                        .where(AuditLog.resource_id == "WEBSITE_EXTERNAL_LINKS")
                        .where(AuditLog.action == "UPDATE")
                    )
                ).scalar()
                or 0
            )
            assert n == 1

    asyncio.run(_assert_audit_once())


