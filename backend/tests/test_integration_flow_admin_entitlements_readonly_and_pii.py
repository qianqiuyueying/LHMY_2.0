"""集成测试：FLOW-ADMIN-ENTITLEMENTS（只读监管：RBAC + Admin 禁止凭证明文）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9O
  - /entitlements：仅允许 ADMIN/USER；DEALER/PROVIDER 等有效 token 必须 403 FORBIDDEN；未携带/无效 token 401 UNAUTHENTICATED
  - Admin 场景禁止返回 qrCode/voucherCode（列表/详情）
- specs-prod/admin/tasks.md#FLOW-ADMIN-ENTITLEMENTS
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
from app.models.user import User
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
from app.utils.jwt_dealer_token import create_dealer_token
from app.utils.jwt_provider_token import create_provider_token
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


async def _seed_user_and_entitlement(*, user_id: str, entitlement_id: str) -> None:
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(User(id=user_id, phone="13600000000", nickname="u", identities=[]))
        session.add(
            Entitlement(
                id=entitlement_id,
                user_id=user_id,
                owner_id=user_id,
                order_id=str(uuid4()),
                entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                service_type="SVC:DEMO",
                remaining_count=1,
                total_count=1,
                valid_from=now - timedelta(days=1),
                valid_until=now + timedelta(days=30),
                applicable_venues=None,
                applicable_regions=["CITY:110100"],
                qr_code="PLAINTEXT_QR_PAYLOAD_SHOULD_NOT_LEAK_TO_ADMIN",
                voucher_code="PLAINTEXT_VOUCHER_SHOULD_NOT_LEAK_TO_ADMIN",
                status=EntitlementStatus.ACTIVE.value,
                service_package_instance_id=None,
                activator_id="",
                current_user_id="",
                created_at=now,
            )
        )
        await session.commit()


def test_entitlements_only_allow_admin_or_user_and_admin_response_has_no_qr_or_voucher():
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    user_id = str(uuid4())
    entitlement_id = str(uuid4())
    asyncio.run(_seed_user_and_entitlement(user_id=user_id, entitlement_id=entitlement_id))

    # 未登录 -> 401
    r0 = client.get("/api/v1/entitlements")
    assert r0.status_code == 401
    assert r0.json()["error"]["code"] == "UNAUTHENTICATED"

    # DEALER/PROVIDER token -> 403 FORBIDDEN（有效 token，但角色不允许）
    dealer_token, _ = create_dealer_token(actor_id=str(uuid4()))
    r_dealer = client.get("/api/v1/entitlements", headers={"Authorization": f"Bearer {dealer_token}"})
    assert r_dealer.status_code == 403
    assert r_dealer.json()["error"]["code"] == "FORBIDDEN"

    provider_token, _ = create_provider_token(actor_type="PROVIDER", actor_id=str(uuid4()))
    r_provider = client.get("/api/v1/entitlements", headers={"Authorization": f"Bearer {provider_token}"})
    assert r_provider.status_code == 403
    assert r_provider.json()["error"]["code"] == "FORBIDDEN"

    # USER -> 200，且可看到自己的凭证字段（不做安全禁止；Admin 禁止才是本卡重点）
    user_token = create_user_token(user_id=user_id, channel="MINI_PROGRAM")
    r_user = client.get("/api/v1/entitlements", headers={"Authorization": f"Bearer {user_token}"})
    assert r_user.status_code == 200
    items_user = r_user.json()["data"]["items"]
    assert len(items_user) >= 1
    assert any(x.get("id") == entitlement_id for x in items_user)
    # user dto 允许包含 qrCode/voucherCode（用于自身核销/展示）

    # ADMIN -> 200，且 list/detail 不得包含 qrCode/voucherCode
    admin_token, _ = create_admin_token(admin_id=str(uuid4()))
    r_admin = client.get("/api/v1/entitlements", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_admin.status_code == 200
    items_admin = r_admin.json()["data"]["items"]
    assert len(items_admin) >= 1
    row = next(x for x in items_admin if x.get("id") == entitlement_id)
    assert "qrCode" not in row
    assert "voucherCode" not in row

    r_admin_detail = client.get(f"/api/v1/entitlements/{entitlement_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_admin_detail.status_code == 200
    d = r_admin_detail.json()["data"]
    assert d["id"] == entitlement_id
    assert "qrCode" not in d
    assert "voucherCode" not in d


