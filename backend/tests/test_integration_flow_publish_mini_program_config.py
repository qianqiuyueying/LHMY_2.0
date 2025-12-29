"""集成测试：FLOW-PUBLISH-MINI-PROGRAM（小程序配置发布/下线：门禁 + 幂等 + 审计）。

规格依据（单一真相来源）：
- specs-prod/admin/security.md#1.4（高风险操作 phone bound）
- specs-prod/admin/api-contracts.md（本批新增：Mini Program Config 发布口径）
- specs-prod/admin/tasks.md#FLOW-PUBLISH-MINI-PROGRAM
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
                username=f"it_admin_mp_{admin_id[-4:]}",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone=phone,
            )
        )
        await session.commit()


async def _audit_count(*, resource_id: str, action: str) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        n = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.resource_type == "MINI_PROGRAM_CONFIG")
                    .where(AuditLog.resource_id == resource_id)
                    .where(AuditLog.action == action)
                )
            ).scalar()
            or 0
        )
        return n


def test_mini_program_config_publish_offline_phone_bound_and_idempotent():
    asyncio.run(_reset_db_and_redis())
    unbound_id = str(uuid4())
    bound_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=unbound_id, phone=None))
    asyncio.run(_seed_admin(admin_id=bound_id, phone="13800138000"))

    unbound_token, _ = create_admin_token(admin_id=unbound_id)
    bound_token, _ = create_admin_token(admin_id=bound_id)
    client = TestClient(app)

    # 准备：写入一个 entry、一个 page、一个 collection（PUT 仅 require_admin）
    entry = {
        "id": "e1",
        "name": "入口1",
        "iconUrl": "",
        "position": "SHORTCUT",
        "jumpType": "WEBVIEW",
        "targetId": "https://example.com",
        "sort": 0,
        "enabled": True,
    }
    r_put_entries = client.put(
        "/api/v1/admin/mini-program/entries",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"items": [entry]},
    )
    assert r_put_entries.status_code == 200

    page_id = "p1"
    r_put_page = client.put(
        f"/api/v1/admin/mini-program/pages/{page_id}",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"type": "INFO_PAGE", "config": {"title": "T1"}},
    )
    assert r_put_page.status_code == 200

    col_id = "c1"
    r_put_col = client.put(
        f"/api/v1/admin/mini-program/collections/{col_id}",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"name": "Col1", "schema": {"type": "x"}, "items": []},
    )
    assert r_put_col.status_code == 200

    # 1) 未绑定手机号：publish entries -> 403
    r1 = client.post(
        "/api/v1/admin/mini-program/entries/publish",
        headers={"Authorization": f"Bearer {unbound_token}"},
    )
    assert r1.status_code == 403
    assert r1.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # 2) entries publish 幂等：首次推进 version + 写审计；重复不推进、不重复审计
    r2 = client.post("/api/v1/admin/mini-program/entries/publish", headers={"Authorization": f"Bearer {bound_token}"})
    assert r2.status_code == 200
    v_pub = str(r2.json()["data"]["version"])
    assert v_pub and v_pub != "0"

    r3 = client.post("/api/v1/admin/mini-program/entries/publish", headers={"Authorization": f"Bearer {bound_token}"})
    assert r3.status_code == 200
    assert str(r3.json()["data"]["version"]) == v_pub
    assert asyncio.run(_audit_count(resource_id="ENTRIES", action="PUBLISH")) == 1

    # 3) entries offline 幂等：首次推进 version + 写审计；重复不推进、不重复审计
    r4 = client.post("/api/v1/admin/mini-program/entries/offline", headers={"Authorization": f"Bearer {bound_token}"})
    assert r4.status_code == 200
    v_off = str(r4.json()["data"]["version"])
    assert v_off and v_off != "0"

    r5 = client.post("/api/v1/admin/mini-program/entries/offline", headers={"Authorization": f"Bearer {bound_token}"})
    assert r5.status_code == 200
    assert str(r5.json()["data"]["version"]) == v_off
    assert asyncio.run(_audit_count(resource_id="ENTRIES", action="OFFLINE")) == 1

    # 4) page publish/offline 幂等 + 审计
    rp1 = client.post(
        f"/api/v1/admin/mini-program/pages/{page_id}/publish", headers={"Authorization": f"Bearer {bound_token}"}
    )
    assert rp1.status_code == 200
    vp = str(rp1.json()["data"]["version"])
    rp2 = client.post(
        f"/api/v1/admin/mini-program/pages/{page_id}/publish", headers={"Authorization": f"Bearer {bound_token}"}
    )
    assert rp2.status_code == 200
    assert str(rp2.json()["data"]["version"]) == vp
    assert asyncio.run(_audit_count(resource_id=f"PAGES:{page_id}", action="PUBLISH")) == 1

    ro1 = client.post(
        f"/api/v1/admin/mini-program/pages/{page_id}/offline", headers={"Authorization": f"Bearer {bound_token}"}
    )
    assert ro1.status_code == 200
    vo = str(ro1.json()["data"]["version"])
    ro2 = client.post(
        f"/api/v1/admin/mini-program/pages/{page_id}/offline", headers={"Authorization": f"Bearer {bound_token}"}
    )
    assert ro2.status_code == 200
    assert str(ro2.json()["data"]["version"]) == vo
    assert asyncio.run(_audit_count(resource_id=f"PAGES:{page_id}", action="OFFLINE")) == 1

    # 5) collection publish/offline 幂等 + 审计
    cp1 = client.post(
        f"/api/v1/admin/mini-program/collections/{col_id}/publish", headers={"Authorization": f"Bearer {bound_token}"}
    )
    assert cp1.status_code == 200
    cpub_v = str(cp1.json()["data"]["version"])
    cp2 = client.post(
        f"/api/v1/admin/mini-program/collections/{col_id}/publish", headers={"Authorization": f"Bearer {bound_token}"}
    )
    assert cp2.status_code == 200
    assert str(cp2.json()["data"]["version"]) == cpub_v
    assert asyncio.run(_audit_count(resource_id=f"COLLECTIONS:{col_id}", action="PUBLISH")) == 1

    co1 = client.post(
        f"/api/v1/admin/mini-program/collections/{col_id}/offline", headers={"Authorization": f"Bearer {bound_token}"}
    )
    assert co1.status_code == 200
    coff_v = str(co1.json()["data"]["version"])
    co2 = client.post(
        f"/api/v1/admin/mini-program/collections/{col_id}/offline", headers={"Authorization": f"Bearer {bound_token}"}
    )
    assert co2.status_code == 200
    assert str(co2.json()["data"]["version"]) == coff_v
    assert asyncio.run(_audit_count(resource_id=f"COLLECTIONS:{col_id}", action="OFFLINE")) == 1


