"""集成测试：FLOW-PUBLISH-CMS（CMS 内容发布/下线：门禁 + 幂等 + 审计）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9G（CMS publish/offline：phone bound + 审计 + no-op + 409）
- specs-prod/admin/tasks.md#FLOW-PUBLISH-CMS
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
from app.models.cms_channel import CmsChannel
from app.models.cms_content import CmsContent
from app.models.enums import AuditAction, AuditActorType, CmsContentStatus
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
                username=f"it_admin_cms_{admin_id[-4:]}",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone=phone,
            )
        )
        await session.commit()


async def _seed_channel_and_content(*, status: str, mp_status: str) -> str:
    cid = str(uuid4())
    ctid = str(uuid4())
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(CmsChannel(id=cid, name="IT Channel", sort=0, status="ENABLED"))
        session.add(
            CmsContent(
                id=ctid,
                channel_id=cid,
                title="IT Content",
                cover_image_url=None,
                summary="s",
                content_md="# hi",
                content_html="<p>hi</p>",
                status=status,
                mp_status=mp_status,
            )
        )
        await session.commit()
    return ctid


def test_cms_publish_offline_phone_bound_idempotent_and_audited():
    asyncio.run(_reset_db_and_redis())

    unbound_admin_id = str(uuid4())
    bound_admin_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=unbound_admin_id, phone=None))
    asyncio.run(_seed_admin(admin_id=bound_admin_id, phone="13800138000"))

    unbound_token, _ = create_admin_token(admin_id=unbound_admin_id)
    bound_token, _ = create_admin_token(admin_id=bound_admin_id)

    content_id = asyncio.run(_seed_channel_and_content(status="DRAFT", mp_status="DRAFT"))
    client = TestClient(app)

    # 1) 未绑定手机号：发布 -> 403 ADMIN_PHONE_REQUIRED
    r1 = client.post(
        f"/api/v1/admin/cms/contents/{content_id}/publish?scope=WEB",
        headers={"Authorization": f"Bearer {unbound_token}"},
    )
    assert r1.status_code == 403
    assert r1.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # 2) 绑定手机号：WEB publish 首次 -> 200，写审计
    r2 = client.post(
        f"/api/v1/admin/cms/contents/{content_id}/publish?scope=WEB",
        headers={"Authorization": f"Bearer {bound_token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert r2.json()["data"]["status"] == "PUBLISHED"

    # 3) WEB publish 重复 -> 200 no-op（不重复写审计）
    r3 = client.post(
        f"/api/v1/admin/cms/contents/{content_id}/publish?scope=WEB",
        headers={"Authorization": f"Bearer {bound_token}"},
    )
    assert r3.status_code == 200
    assert r3.json()["data"]["status"] == "PUBLISHED"

    # 4) WEB offline 首次 -> 200，写审计
    r4 = client.post(
        f"/api/v1/admin/cms/contents/{content_id}/offline?scope=WEB",
        headers={"Authorization": f"Bearer {bound_token}"},
    )
    assert r4.status_code == 200
    assert r4.json()["data"]["status"] == "OFFLINE"

    # 5) WEB offline 重复 -> 200 no-op（不重复写审计）
    r5 = client.post(
        f"/api/v1/admin/cms/contents/{content_id}/offline?scope=WEB",
        headers={"Authorization": f"Bearer {bound_token}"},
    )
    assert r5.status_code == 200
    assert r5.json()["data"]["status"] == "OFFLINE"

    async def _assert_audit_counts() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            n_pub = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(AuditLog)
                        .where(AuditLog.actor_type == AuditActorType.ADMIN.value)
                        .where(AuditLog.action == AuditAction.PUBLISH.value)
                        .where(AuditLog.resource_type == "CMS_CONTENT")
                        .where(AuditLog.resource_id == content_id)
                    )
                ).scalar()
                or 0
            )
            n_off = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(AuditLog)
                        .where(AuditLog.actor_type == AuditActorType.ADMIN.value)
                        .where(AuditLog.action == AuditAction.OFFLINE.value)
                        .where(AuditLog.resource_type == "CMS_CONTENT")
                        .where(AuditLog.resource_id == content_id)
                    )
                ).scalar()
                or 0
            )
            assert n_pub == 1
            assert n_off == 1

    asyncio.run(_assert_audit_counts())


def test_cms_invalid_transitions_return_409_invalid_state_transition():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_id, phone="13800138000"))
    token, _ = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # DRAFT -> OFFLINE 禁止（WEB）
    c1 = asyncio.run(_seed_channel_and_content(status="DRAFT", mp_status="DRAFT"))
    r1 = client.post(f"/api/v1/admin/cms/contents/{c1}/offline?scope=WEB", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 409
    assert r1.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # DRAFT -> OFFLINE 禁止（MINI_PROGRAM）
    r2 = client.post(
        f"/api/v1/admin/cms/contents/{c1}/offline?scope=MINI_PROGRAM", headers={"Authorization": f"Bearer {token}"}
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


