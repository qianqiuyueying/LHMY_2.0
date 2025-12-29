"""集成测试：权限 DoD 用例护栏（TASK-P0-001）。

规格依据（单一真相来源）：
- specs-prod/admin/requirements.md#3 DoD（DoD-CASE-002/004/005）
- specs-prod/admin/tasks.md#TASK-P0-001

覆盖范围（最小但可阻断回归）：
- UNAUTHENTICATED：未登录调用 /api/v1/admin/** -> 401 + UNAUTHENTICATED
- FORBIDDEN：非 ADMIN token 调用 /api/v1/admin/** -> 403 + FORBIDDEN
- 资源归属越权：PROVIDER 尝试对非本 provider 的 venueId 发起核销 -> 403 + FORBIDDEN
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.entitlement import Entitlement
from app.models.enums import EntitlementStatus, EntitlementType
from app.models.provider import Provider
from app.models.provider_user import ProviderUser
from app.models.venue import Venue
from app.services.password_hashing import hash_password
from app.utils.db import get_session_factory
from app.utils.jwt_dealer_token import create_dealer_token
from app.utils.jwt_provider_token import create_provider_token
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


def _assert_fail_envelope(resp_json: dict, *, code: str) -> None:
    # 约束：全局异常应转换为统一 envelope（success/data/error/requestId）
    assert resp_json.get("success") is False
    assert resp_json.get("data") is None
    assert resp_json.get("error", {}).get("code") == code
    assert isinstance(resp_json.get("error", {}).get("message"), str)
    assert isinstance(resp_json.get("requestId"), str)


def test_dod_case_unauthenticated_admin_api_401():
    """DoD-CASE-002：未登录调用受保护 API -> 401 UNAUTHENTICATED。"""
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    r = client.get("/api/v1/admin/users", params={"page": 1, "pageSize": 1})
    assert r.status_code == 401
    _assert_fail_envelope(r.json(), code="UNAUTHENTICATED")


def test_dod_case_role_mismatch_admin_api_403():
    """DoD-CASE-004：错误角色调用 admin API -> 403 FORBIDDEN。"""
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    dealer_token, _jti = create_dealer_token(actor_id=str(uuid4()))
    r = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {dealer_token}"},
        params={"page": 1, "pageSize": 1},
    )
    assert r.status_code == 403
    _assert_fail_envelope(r.json(), code="FORBIDDEN")


def test_dod_case_provider_cross_resource_forbidden_403():
    """DoD-CASE-005：PROVIDER 以他人 venueId 执行敏感操作 -> 403 FORBIDDEN。"""
    asyncio.run(_reset_db_and_redis())

    # seed：providerA 账号、providerB 的 venue、以及一条 ACTIVE entitlement（使流程走到 ownership 校验）
    provider_a_id = str(uuid4())
    provider_b_id = str(uuid4())
    provider_user_id = str(uuid4())
    foreign_venue_id = str(uuid4())
    entitlement_id = str(uuid4())
    user_id = str(uuid4())
    order_id = str(uuid4())

    now = datetime.now(tz=UTC).replace(tzinfo=None)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(Provider(id=provider_a_id, name="IT Provider A"))
            session.add(Provider(id=provider_b_id, name="IT Provider B"))
            session.add(
                ProviderUser(
                    id=provider_user_id,
                    provider_id=provider_a_id,
                    username="it_provider_user_authz_1",
                    password_hash=hash_password(password="P@ssw0rd_authz_1"),
                    status="ACTIVE",
                )
            )
            session.add(
                Venue(
                    id=foreign_venue_id,
                    provider_id=provider_b_id,  # 非本 provider
                    name="Foreign Venue",
                    publish_status="PUBLISHED",
                )
            )
            session.add(
                Entitlement(
                    id=entitlement_id,
                    user_id=user_id,
                    owner_id=user_id,
                    order_id=order_id,
                    entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                    service_type="IT_SERVICE_TYPE",
                    remaining_count=1,
                    total_count=1,
                    valid_from=(now - timedelta(days=1)),
                    valid_until=(now + timedelta(days=30)),
                    applicable_venues=None,
                    applicable_regions=None,
                    qr_code="it_qr_payload_dummy",
                    voucher_code="ITVOUCHERDUMMY",
                    status=EntitlementStatus.ACTIVE.value,
                    service_package_instance_id=None,
                    activator_id=user_id,
                    current_user_id=user_id,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    provider_token, _jti2 = create_provider_token(actor_type="PROVIDER", actor_id=provider_user_id)
    client = TestClient(app)

    r = client.post(
        f"/api/v1/entitlements/{entitlement_id}/redeem",
        headers={"Authorization": f"Bearer {provider_token}", "Idempotency-Key": uuid4().hex},
        json={"venueId": foreign_venue_id, "redemptionMethod": "QR_CODE", "voucherCode": "dummy"},
    )
    assert r.status_code == 403
    _assert_fail_envelope(r.json(), code="FORBIDDEN")


