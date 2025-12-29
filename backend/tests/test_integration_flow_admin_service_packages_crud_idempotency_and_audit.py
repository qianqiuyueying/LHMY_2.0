"""集成测试：FLOW-ADMIN-SERVICE-PACKAGES（服务包模板管理：phone bound + 幂等 + 审计 + locked 规则）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9Q
  - POST/PUT：require_admin_phone_bound；POST 强制 Idempotency-Key
  - 字段校验失败收敛 400 INVALID_ARGUMENT（不走 422）
  - POST/PUT（非 no-op）必须写审计：resourceType=SERVICE_PACKAGE_TEMPLATE；幂等复放不重复写审计；no-op 不写审计
  - locked=true 时禁止修改 regionLevel/tier/services（409 STATE_CONFLICT）
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
from app.models.enums import CommonEnabledStatus
from app.models.package_service import PackageService
from app.models.service_category import ServiceCategory
from app.models.service_package_instance import ServicePackageInstance
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
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Admin(
                id=admin_id,
                username=f"u_{admin_id[:8]}",
                password_hash="bcrypt:$2b$12$dummy",
                status="ACTIVE",
                phone=phone,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


async def _seed_service_category(*, code: str, status: str = CommonEnabledStatus.ENABLED.value) -> None:
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            ServiceCategory(
                id=str(uuid4()),
                code=code,
                display_name=f"cat_{code}",
                status=status,
                sort=0,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


async def _count_template_audits() -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count()).select_from(AuditLog).where(AuditLog.resource_type == "SERVICE_PACKAGE_TEMPLATE")
                )
            ).scalar()
            or 0
        )


async def _insert_instance(*, template_id: str, owner_id: str) -> None:
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            ServicePackageInstance(
                id=str(uuid4()),
                order_id=str(uuid4()),
                order_item_id=str(uuid4()),
                service_package_template_id=template_id,
                owner_id=owner_id,
                region_scope="CITY:110100",
                tier="DEFAULT",
                valid_from=now,
                valid_until=now,
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


def test_service_packages_create_idempotency_audit_and_locked_update_rules():
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    # seed category
    asyncio.run(_seed_service_category(code="SVC_A"))

    # phone 未绑定：写操作门禁 403 ADMIN_PHONE_REQUIRED
    admin_unbound = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_unbound, phone=None))
    token_unbound, _ = create_admin_token(admin_id=admin_unbound)
    r_unbound = client.post(
        "/api/v1/admin/service-packages",
        headers={"Authorization": f"Bearer {token_unbound}", "Idempotency-Key": "k1"},
        json={
            "name": "t1",
            "regionLevel": "CITY",
            "tier": "DEFAULT",
            "description": None,
            "services": [{"serviceType": "SVC_A", "totalCount": 1}],
        },
    )
    assert r_unbound.status_code == 403
    assert r_unbound.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # phone 已绑定：缺少 Idempotency-Key -> 400 INVALID_ARGUMENT（不走 422）
    admin_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_id, phone="13600000000"))
    token, _ = create_admin_token(admin_id=admin_id)
    r_missing_key = client.post(
        "/api/v1/admin/service-packages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "t1",
            "regionLevel": "CITY",
            "tier": "DEFAULT",
            "description": None,
            "services": [{"serviceType": "SVC_A", "totalCount": 1}],
        },
    )
    assert r_missing_key.status_code == 400
    assert r_missing_key.json()["error"]["code"] == "INVALID_ARGUMENT"

    # create：成功 + 写审计 1 条；重放同 key 返回同 id，不重复写审计
    r1 = client.post(
        "/api/v1/admin/service-packages",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-create-1"},
        json={
            "name": "t1",
            "regionLevel": "CITY",
            "tier": "DEFAULT",
            "description": "d",
            "services": [{"serviceType": "SVC_A", "totalCount": 1}],
        },
    )
    assert r1.status_code == 200
    template_id = r1.json()["data"]["id"]
    assert template_id
    assert asyncio.run(_count_template_audits()) == 1

    r1_replay = client.post(
        "/api/v1/admin/service-packages",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "k-create-1"},
        json={
            "name": "t1",
            "regionLevel": "CITY",
            "tier": "DEFAULT",
            "description": "d",
            "services": [{"serviceType": "SVC_A", "totalCount": 1}],
        },
    )
    assert r1_replay.status_code == 200
    assert r1_replay.json()["data"]["id"] == template_id
    assert asyncio.run(_count_template_audits()) == 1

    # PUT no-op：不写审计
    r_noop = client.put(
        f"/api/v1/admin/service-packages/{template_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "t1",
            "regionLevel": "CITY",
            "tier": "DEFAULT",
            "description": "d",
            "services": [{"serviceType": "SVC_A", "totalCount": 1}],
        },
    )
    assert r_noop.status_code == 200
    assert r_noop.json()["data"]["locked"] is False
    assert asyncio.run(_count_template_audits()) == 1

    # locked 后：禁止修改 regionLevel/tier/services（409），允许改 name/description 并写审计
    asyncio.run(_insert_instance(template_id=template_id, owner_id=str(uuid4())))

    r_locked_bad = client.put(
        f"/api/v1/admin/service-packages/{template_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "t1",
            "regionLevel": "PROVINCE",
            "tier": "DEFAULT",
            "description": "d",
            "services": [{"serviceType": "SVC_A", "totalCount": 1}],
        },
    )
    assert r_locked_bad.status_code == 409
    assert r_locked_bad.json()["error"]["code"] == "STATE_CONFLICT"

    r_locked_ok = client.put(
        f"/api/v1/admin/service-packages/{template_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "t1_new",
            "regionLevel": "CITY",
            "tier": "DEFAULT",
            "description": "d2",
            "services": [{"serviceType": "SVC_A", "totalCount": 1}],
        },
    )
    assert r_locked_ok.status_code == 200
    assert r_locked_ok.json()["data"]["locked"] is True
    assert asyncio.run(_count_template_audits()) == 2


