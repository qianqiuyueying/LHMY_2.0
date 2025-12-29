"""集成测试：FLOW-ADMIN-ENTERPRISE（企业与绑定审核：门禁 + 幂等 + 审计 + 错误码）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9M（phone bound 门禁、200 no-op、409 INVALID_STATE_TRANSITION、审计 resourceType）
- specs-prod/admin/tasks.md#FLOW-ADMIN-ENTERPRISE
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
from app.models.enterprise import Enterprise
from app.models.user import User
from app.models.user_enterprise_binding import UserEnterpriseBinding
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
                username=f"it_admin_enterprise_{admin_id[-4:]}",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone=phone,
            )
        )
        await session.commit()


async def _seed_enterprise_and_user_and_binding(*, status: str) -> tuple[str, str, str]:
    enterprise_id = str(uuid4())
    user_id = str(uuid4())
    binding_id = str(uuid4())

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Enterprise(
                id=enterprise_id,
                name="IT Enterprise",
                country_code="COUNTRY:CN",
                province_code="PROVINCE:110000",
                city_code="CITY:110100",
                source="MANUAL",
                first_seen_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            User(
                id=user_id,
                phone="13800138000",
                openid=None,
                unionid=None,
                nickname="",
                avatar=None,
                identities=[],
                enterprise_id=None,
                enterprise_name=None,
                binding_time=None,
            )
        )
        session.add(
            UserEnterpriseBinding(
                id=binding_id,
                user_id=user_id,
                enterprise_id=enterprise_id,
                status=status,
                binding_time=now,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    return binding_id, user_id, enterprise_id


async def _count_audit(*, resource_type: str, resource_id: str, action: str) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        n = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.resource_type == resource_type)
                    .where(AuditLog.resource_id == resource_id)
                    .where(AuditLog.action == action)
                )
            ).scalar()
            or 0
        )
        return n


def test_enterprise_binding_approve_reject_require_phone_bound_and_are_idempotent_and_audited():
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    unbound_admin_id = str(uuid4())
    bound_admin_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=unbound_admin_id, phone=None))
    asyncio.run(_seed_admin(admin_id=bound_admin_id, phone="13800138000"))

    unbound_token, _ = create_admin_token(admin_id=unbound_admin_id)
    bound_token, _ = create_admin_token(admin_id=bound_admin_id)

    # seed PENDING binding
    binding_id, _user_id, _enterprise_id = asyncio.run(_seed_enterprise_and_user_and_binding(status="PENDING"))

    # 未绑定手机号 -> 403 ADMIN_PHONE_REQUIRED
    r_forbidden = client.put(
        f"/api/v1/admin/enterprise-bindings/{binding_id}/approve",
        headers={"Authorization": f"Bearer {unbound_token}"},
    )
    assert r_forbidden.status_code == 403
    assert r_forbidden.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # 通过：PENDING -> APPROVED，写审计
    r_ok = client.put(
        f"/api/v1/admin/enterprise-bindings/{binding_id}/approve",
        headers={"Authorization": f"Bearer {bound_token}"},
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["data"]["status"] == "APPROVED"
    assert asyncio.run(_count_audit(resource_type="ENTERPRISE_BINDING_REVIEW", resource_id=binding_id, action="UPDATE")) == 1

    # 再次 approve -> 200 no-op，不重复审计
    r_noop = client.put(
        f"/api/v1/admin/enterprise-bindings/{binding_id}/approve",
        headers={"Authorization": f"Bearer {bound_token}"},
    )
    assert r_noop.status_code == 200
    assert r_noop.json()["data"]["status"] == "APPROVED"
    assert asyncio.run(_count_audit(resource_type="ENTERPRISE_BINDING_REVIEW", resource_id=binding_id, action="UPDATE")) == 1

    # 已 APPROVED 再 reject -> 409 INVALID_STATE_TRANSITION
    r_invalid = client.put(
        f"/api/v1/admin/enterprise-bindings/{binding_id}/reject",
        headers={"Authorization": f"Bearer {bound_token}"},
    )
    assert r_invalid.status_code == 409
    assert r_invalid.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # seed another binding PENDING，走 reject
    asyncio.run(_reset_db_and_redis())
    asyncio.run(_seed_admin(admin_id=bound_admin_id, phone="13800138000"))
    bound_token2, _ = create_admin_token(admin_id=bound_admin_id)
    binding_id2, _user_id2, _enterprise_id2 = asyncio.run(_seed_enterprise_and_user_and_binding(status="PENDING"))

    r_reject = client.put(
        f"/api/v1/admin/enterprise-bindings/{binding_id2}/reject",
        headers={"Authorization": f"Bearer {bound_token2}"},
    )
    assert r_reject.status_code == 200
    assert r_reject.json()["data"]["status"] == "REJECTED"
    assert asyncio.run(_count_audit(resource_type="ENTERPRISE_BINDING_REVIEW", resource_id=binding_id2, action="UPDATE")) == 1

    # 再次 reject -> 200 no-op，不重复审计
    r_reject_noop = client.put(
        f"/api/v1/admin/enterprise-bindings/{binding_id2}/reject",
        headers={"Authorization": f"Bearer {bound_token2}"},
    )
    assert r_reject_noop.status_code == 200
    assert r_reject_noop.json()["data"]["status"] == "REJECTED"
    assert asyncio.run(_count_audit(resource_type="ENTERPRISE_BINDING_REVIEW", resource_id=binding_id2, action="UPDATE")) == 1

    # 已 REJECTED 再 approve -> 409 INVALID_STATE_TRANSITION
    r_invalid2 = client.put(
        f"/api/v1/admin/enterprise-bindings/{binding_id2}/approve",
        headers={"Authorization": f"Bearer {bound_token2}"},
    )
    assert r_invalid2.status_code == 409
    assert r_invalid2.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_enterprise_update_name_requires_phone_bound_and_writes_audit():
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    unbound_admin_id = str(uuid4())
    bound_admin_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=unbound_admin_id, phone=None))
    asyncio.run(_seed_admin(admin_id=bound_admin_id, phone="13800138000"))

    unbound_token, _ = create_admin_token(admin_id=unbound_admin_id)
    bound_token, _ = create_admin_token(admin_id=bound_admin_id)

    # seed enterprise
    session_factory = get_session_factory()
    enterprise_id = str(uuid4())
    now = datetime.now(tz=UTC)

    async def _seed_enterprise_only() -> None:
        async with session_factory() as session:
            session.add(
                Enterprise(
                    id=enterprise_id,
                    name="Old Name",
                    country_code="COUNTRY:CN",
                    province_code="PROVINCE:110000",
                    city_code="CITY:110100",
                    source="MANUAL",
                    first_seen_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
    asyncio.run(_seed_enterprise_only())

    # unbound -> 403
    r_forbidden = client.put(
        f"/api/v1/admin/enterprises/{enterprise_id}",
        headers={"Authorization": f"Bearer {unbound_token}"},
        json={"name": "New Name"},
    )
    assert r_forbidden.status_code == 403
    assert r_forbidden.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # bound -> 200 + audit
    r_ok = client.put(
        f"/api/v1/admin/enterprises/{enterprise_id}",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"name": "New Name"},
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["data"]["name"] == "New Name"
    assert asyncio.run(_count_audit(resource_type="ENTERPRISE", resource_id=enterprise_id, action="UPDATE")) == 1


