"""集成测试：RBAC 隔离 + 敏感操作审计（Go-Live gates 最小证据）。

规格来源：
- specs/功能实现/admin/tasks.md -> T-F04
- specs/功能实现/admin/rbac.md

说明：
- 该测试不追求覆盖所有接口，只证明：
  1) Admin/Provider/Dealer token 隔离生效（越权访问返回 401/403 + 可区分错误码）
  2) 管理员执行敏感写操作后，可在审计日志里查询到记录（最小证据）
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


def _assert_fail_payload(resp_json: dict) -> None:
    assert resp_json.get("success") is False
    assert isinstance(resp_json.get("error", {}).get("code"), str)
    assert isinstance(resp_json.get("error", {}).get("message"), str)


def test_rbac_isolation_and_audit_log_minimal_evidence():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # FLOW-ACCOUNTS 高风险门禁：写操作要求 admin 绑定手机号
    async def _seed_admin_phone_bound() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Admin(
                    id=admin_id,
                    username="it_admin_gate",
                    password_hash=hash_password(password="Abcdef!2345"),
                    status="ACTIVE",
                    phone="13800138000",
                )
            )
            await session.commit()

    asyncio.run(_seed_admin_phone_bound())

    # 1) Admin 创建 Provider/Dealer 账号（敏感写操作，应触发审计）
    r = client.post(
        "/api/v1/admin/provider-users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "it_provider_user_1", "providerName": "IT Provider 1"},
    )
    assert r.status_code == 200
    provider_password = r.json()["data"]["password"]

    r = client.post(
        "/api/v1/admin/dealer-users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "it_dealer_user_1", "dealerName": "IT Dealer 1"},
    )
    assert r.status_code == 200
    dealer_password = r.json()["data"]["password"]

    # 2) Provider/Dealer 登录拿到各自 token
    r = client.post("/api/v1/provider/auth/login", json={"username": "it_provider_user_1", "password": provider_password})
    assert r.status_code == 200
    provider_token = r.json()["data"]["token"]

    r = client.post("/api/v1/dealer/auth/login", json={"username": "it_dealer_user_1", "password": dealer_password})
    assert r.status_code == 200
    dealer_token = r.json()["data"]["token"]

    # 3) 越权访问（token 隔离）
    # - Provider token 访问 Admin-only
    r = client.get("/api/v1/admin/dashboard/summary", headers={"Authorization": f"Bearer {provider_token}"})
    assert r.status_code in {401, 403}
    _assert_fail_payload(r.json())

    # - Dealer token 访问 Admin-only
    r = client.get("/api/v1/admin/dashboard/summary", headers={"Authorization": f"Bearer {dealer_token}"})
    assert r.status_code in {401, 403}
    _assert_fail_payload(r.json())

    # - Admin token 访问 Provider-only
    r = client.get("/api/v1/provider/workbench/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code in {401, 403}
    _assert_fail_payload(r.json())

    # 4) 审计日志：最小证据（管理员执行过写操作，应能查到至少一条）
    r = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"page": 1, "pageSize": 50},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert isinstance(data.get("items"), list)
    assert data.get("total", 0) >= 1

