"""集成测试：Admin 审计日志查询（RBAC 语义 + metadata 脱敏，Batch7）。

规格来源（单一真相来源）：
- specs-prod/admin/tasks.md#FLOW-AUDIT-LOGS
- specs-prod/admin/security.md#3 审计
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
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
from app.utils.jwt_dealer_token import create_dealer_token
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


def test_admin_audit_logs_rbac_and_masking():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # 预置一条脏 metadata（包含 password/token/phone），用于验证出参兜底脱敏
    audit_id = str(uuid4())

    async def _seed_log() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                AuditLog(
                    id=audit_id,
                    actor_type="ADMIN",
                    actor_id=admin_id,
                    action="UPDATE",
                    resource_type="IT_TEST",
                    resource_id="it1",
                    summary="it audit",
                    ip="127.0.0.1",
                    user_agent="pytest",
                    metadata_json={
                        "password": "p",
                        "token": "t",
                        "phone": "13800001234",
                        "nested": {"authorization": "Bearer xxx", "smsCode": "1234"},
                    },
                    created_at=datetime.now(tz=UTC).replace(tzinfo=None),
                )
            )
            await session.commit()

    asyncio.run(_seed_log())

    # 401：未登录
    r = client.get("/api/v1/admin/audit-logs", params={"page": 1, "pageSize": 20})
    assert r.status_code == 401

    # 403：非 ADMIN token（dealer）
    dealer_token, _jti2 = create_dealer_token(actor_id=str(uuid4()))
    r = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {dealer_token}"},
        params={"page": 1, "pageSize": 20},
    )
    assert r.status_code == 403

    # 200：ADMIN 查询 + 脱敏断言
    r = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"resourceType": "IT_TEST", "resourceId": "it1", "page": 1, "pageSize": 20},
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) == 1
    # Spec: createdAt must be UTC ISO8601 with Z suffix
    assert items[0]["createdAt"].endswith("Z")
    meta = items[0]["metadata"]
    assert meta["password"] == "***"
    assert meta["token"] == "***"
    assert meta["nested"]["authorization"] == "***"
    assert meta["nested"]["smsCode"] == "***"
    assert meta["phone"] == "138****1234"


