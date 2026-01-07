"""集成测试：Dealer Links（投放链接）幂等 + 审计（Batch3）。

规格来源（单一真相来源）：
- specs-prod/admin/api-contracts.md#9C 投放链接（Dealer Links）
- specs-prod/admin/api-contracts.md#10(8)（你已拍板：POST /dealer-links 强制 Idempotency-Key）
- specs-prod/admin/tasks.md#FLOW-DEALER-LINKS
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
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


async def _seed_admin_phone_bound(*, admin_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Admin(
                id=admin_id,
                username="it_admin_dealer_links",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone="13800138000",
            )
        )
        await session.commit()


def test_dealer_links_create_idempotent_and_audited_and_disable_idempotent():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)
    asyncio.run(_seed_admin_phone_bound(admin_id=admin_id))

    # 1) Admin 创建 dealer 账号并登录拿到 dealer token
    r = client.post(
        "/api/v1/admin/dealer-users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "it_dealer_user_links_1", "dealerName": "IT Dealer Links 1"},
    )
    assert r.status_code == 200
    dealer_password = r.json()["data"]["password"]

    r = client.post("/api/v1/dealer/auth/login", json={"username": "it_dealer_user_links_1", "password": dealer_password})
    assert r.status_code == 200
    dealer_token = r.json()["data"]["token"]

    # 2) 创建入口链接（sellableCardId=null）：强制 Idempotency-Key
    idem_key = "it:dealer-links:create:1"
    r1 = client.post(
        "/api/v1/dealer-links",
        headers={"Authorization": f"Bearer {dealer_token}", "Idempotency-Key": idem_key},
        json={"sellableCardId": None, "campaign": None, "validFrom": None, "validUntil": "2026-01-31"},
    )
    assert r1.status_code == 200
    assert r1.json()["success"] is True
    link_id = r1.json()["data"]["id"]

    # 3) 重复提交同 Idempotency-Key：返回同一条记录（id 不变）
    r2 = client.post(
        "/api/v1/dealer-links",
        headers={"Authorization": f"Bearer {dealer_token}", "Idempotency-Key": idem_key},
        json={"sellableCardId": None, "campaign": None, "validFrom": None, "validUntil": "2026-01-31"},
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert r2.json()["data"]["id"] == link_id

    # 4) 审计：业务审计 resourceType=DEALER_LINK 必须至少 1 条（CREATE）
    r_audit = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"resourceType": "DEALER_LINK", "resourceId": link_id, "page": 1, "pageSize": 50},
    )
    assert r_audit.status_code == 200
    assert r_audit.json()["data"]["total"] >= 1

    # 5) 停用：第一次 ENABLED -> DISABLED
    r3 = client.post(
        f"/api/v1/dealer-links/{link_id}/disable",
        headers={"Authorization": f"Bearer {dealer_token}"},
    )
    assert r3.status_code == 200
    assert r3.json()["success"] is True
    assert r3.json()["data"]["status"] in {"DISABLED", "EXPIRED"}

    # 6) 停用幂等 no-op：第二次停用仍 200，且不重复写业务审计（资源类型=DEALER_LINK）
    r4 = client.post(
        f"/api/v1/dealer-links/{link_id}/disable",
        headers={"Authorization": f"Bearer {dealer_token}"},
    )
    assert r4.status_code == 200
    assert r4.json()["success"] is True

    async def _count_business_audit() -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(func.count()).select_from(AuditLog).where(
                AuditLog.resource_type == "DEALER_LINK",
                AuditLog.resource_id == link_id,
            )
            return int((await session.execute(stmt)).scalar() or 0)

    # 预期：CREATE 1 条 + DISABLE 1 条；no-op 不追加
    assert asyncio.run(_count_business_audit()) == 2


def test_dealer_links_create_requires_idempotency_key_400():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)
    asyncio.run(_seed_admin_phone_bound(admin_id=admin_id))

    username = f"it_dealer_user_links_{uuid4().hex[:8]}"
    r = client.post(
        "/api/v1/admin/dealer-users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": username, "dealerName": "IT Dealer Links 2"},
    )
    assert r.status_code == 200
    dealer_password = r.json()["data"]["password"]

    r = client.post("/api/v1/dealer/auth/login", json={"username": username, "password": dealer_password})
    assert r.status_code == 200
    dealer_token = r.json()["data"]["token"]

    r2 = client.post(
        "/api/v1/dealer-links",
        headers={"Authorization": f"Bearer {dealer_token}"},
        json={"sellableCardId": None, "campaign": None, "validFrom": None, "validUntil": "2026-01-31"},
    )
    assert r2.status_code == 400
    payload = r2.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"


