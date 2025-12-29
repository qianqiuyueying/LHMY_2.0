"""集成测试：FLOW-REVIEW-VENUES（发布/下线 幂等 + 审计）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#1.4（状态机写操作：同目标状态重复提交 -> 200 no-op）
- specs-prod/admin/tasks.md#FLOW-REVIEW-VENUES
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
from app.models.provider import Provider
from app.models.venue import Venue
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
                username="it_admin_venues",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone="13800138000",
            )
        )
        await session.commit()


async def _seed_provider_and_venue(*, publish_status: str) -> str:
    provider_id = str(uuid4())
    venue_id = str(uuid4())
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(Provider(id=provider_id, name="IT Provider"))
        session.add(Venue(id=venue_id, provider_id=provider_id, name="IT Venue", publish_status=publish_status))
        await session.commit()
    return venue_id


def test_review_venues_publish_and_offline_idempotent_noop_and_audited_once():
    asyncio.run(_reset_db_and_redis())
    admin_id = "00000000-0000-0000-0000-00000000a900"
    asyncio.run(_seed_admin_phone_bound(admin_id=admin_id))
    admin_token, _ = create_admin_token(admin_id=admin_id)
    venue_id = asyncio.run(_seed_provider_and_venue(publish_status="DRAFT"))

    client = TestClient(app)

    # publish 首次：写审计
    r1 = client.post(f"/api/v1/admin/venues/{venue_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})
    assert r1.status_code == 200
    assert r1.json()["success"] is True
    assert r1.json()["data"]["publishStatus"] == "PUBLISHED"

    # publish 重复：200 no-op（不刷审计）
    r2 = client.post(f"/api/v1/admin/venues/{venue_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert r2.json()["data"]["publishStatus"] == "PUBLISHED"

    # offline 首次：写审计
    r3 = client.post(f"/api/v1/admin/venues/{venue_id}/offline", headers={"Authorization": f"Bearer {admin_token}"})
    assert r3.status_code == 200
    assert r3.json()["data"]["publishStatus"] == "OFFLINE"

    # offline 重复：200 no-op（不刷审计）
    r4 = client.post(f"/api/v1/admin/venues/{venue_id}/offline", headers={"Authorization": f"Bearer {admin_token}"})
    assert r4.status_code == 200
    assert r4.json()["data"]["publishStatus"] == "OFFLINE"

    async def _assert_audit_counts() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            n_publish = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(AuditLog)
                        .where(AuditLog.resource_type == "VENUE")
                        .where(AuditLog.resource_id == venue_id)
                        .where(AuditLog.action == "PUBLISH")
                    )
                ).scalar()
                or 0
            )
            n_offline = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(AuditLog)
                        .where(AuditLog.resource_type == "VENUE")
                        .where(AuditLog.resource_id == venue_id)
                        .where(AuditLog.action == "OFFLINE")
                    )
                ).scalar()
                or 0
            )
            assert n_publish == 1
            assert n_offline == 1

    asyncio.run(_assert_audit_counts())


def test_review_venues_invalid_transitions_return_409_invalid_state_transition():
    asyncio.run(_reset_db_and_redis())
    admin_id = "00000000-0000-0000-0000-00000000a901"
    asyncio.run(_seed_admin_phone_bound(admin_id=admin_id))
    admin_token, _ = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # 1) DRAFT -> OFFLINE 禁止
    v1 = asyncio.run(_seed_provider_and_venue(publish_status="DRAFT"))
    r1 = client.post(f"/api/v1/admin/venues/{v1}/offline", headers={"Authorization": f"Bearer {admin_token}"})
    assert r1.status_code == 409
    assert r1.json()["success"] is False
    assert r1.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # 2) PUBLISHED -> DRAFT（reject）禁止
    v2 = asyncio.run(_seed_provider_and_venue(publish_status="PUBLISHED"))
    r2 = client.post(f"/api/v1/admin/venues/{v2}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert r2.status_code == 409
    assert r2.json()["success"] is False
    assert r2.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


