"""集成测试：FLOW-ADMIN-SELLABLE-CARDS（可售卡启停用：phone bound + 审计 + no-op + 400 收敛）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9S
  - POST/PUT/enable/disable：require_admin_phone_bound
  - 请求体校验失败收敛 400 INVALID_ARGUMENT（不走 422）
  - enable/disable：已在目标状态 -> 200 no-op（不写审计）
  - 审计：resourceType=SELLABLE_CARD；enable/disable action=UPDATE
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
from app.models.sellable_card import SellableCard
from app.models.service_package import ServicePackage
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


async def _seed_service_package(*, template_id: str, region_level: str) -> None:
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            ServicePackage(
                id=template_id,
                name="tpl",
                region_level=region_level,
                tier="DEFAULT",
                description=None,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


async def _count_sellable_card_audits() -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        return int(
            (await session.execute(select(func.count()).select_from(AuditLog).where(AuditLog.resource_type == "SELLABLE_CARD")))
            .scalar()
            or 0
        )


def test_sellable_cards_phone_bound_400_no_422_noop_and_audit_and_template_validation():
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    template_id = str(uuid4())
    asyncio.run(_seed_service_package(template_id=template_id, region_level="CITY"))

    # phone 未绑定：写操作门禁 403 ADMIN_PHONE_REQUIRED
    admin_unbound = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_unbound, phone=None))
    token_unbound, _ = create_admin_token(admin_id=admin_unbound)
    r_unbound = client.post(
        "/api/v1/admin/sellable-cards",
        headers={"Authorization": f"Bearer {token_unbound}"},
        json={
            "name": "c1",
            "servicePackageTemplateId": template_id,
            "regionLevel": "CITY",
            "priceOriginal": 0,
            "sort": 0,
        },
    )
    assert r_unbound.status_code == 403
    assert r_unbound.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # phone 已绑定
    admin_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_id, phone="13600000000"))
    token, _ = create_admin_token(admin_id=admin_id)

    # body 非法：必须 400 INVALID_ARGUMENT（不走 422）
    r_bad = client.post(
        "/api/v1/admin/sellable-cards",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "", "servicePackageTemplateId": template_id, "regionLevel": "CITY", "priceOriginal": 0, "sort": 0},
    )
    assert r_bad.status_code == 400
    assert r_bad.json()["error"]["code"] == "INVALID_ARGUMENT"

    # 模板不存在：400 INVALID_ARGUMENT
    r_missing_tpl = client.post(
        "/api/v1/admin/sellable-cards",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "c1",
            "servicePackageTemplateId": str(uuid4()),
            "regionLevel": "CITY",
            "priceOriginal": 0,
            "sort": 0,
        },
    )
    assert r_missing_tpl.status_code == 400
    assert r_missing_tpl.json()["error"]["code"] == "INVALID_ARGUMENT"

    # regionLevel 与模板不一致：400 INVALID_ARGUMENT
    r_mismatch = client.post(
        "/api/v1/admin/sellable-cards",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "c1",
            "servicePackageTemplateId": template_id,
            "regionLevel": "PROVINCE",
            "priceOriginal": 0,
            "sort": 0,
        },
    )
    assert r_mismatch.status_code == 400
    assert r_mismatch.json()["error"]["code"] == "INVALID_ARGUMENT"

    # create 成功：写审计 1 条
    r1 = client.post(
        "/api/v1/admin/sellable-cards",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "c1",
            "servicePackageTemplateId": template_id,
            "regionLevel": "CITY",
            "priceOriginal": 99.9,
            "sort": 1,
        },
    )
    assert r1.status_code == 200
    sellable_id = r1.json()["data"]["id"]
    assert sellable_id
    assert asyncio.run(_count_sellable_card_audits()) == 1

    # enable no-op（已 ENABLED）：200 且不写审计
    r_enable_noop = client.post(
        f"/api/v1/admin/sellable-cards/{sellable_id}/enable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_enable_noop.status_code == 200
    assert asyncio.run(_count_sellable_card_audits()) == 1

    # disable：写审计 +1
    r_disable = client.post(
        f"/api/v1/admin/sellable-cards/{sellable_id}/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_disable.status_code == 200
    assert r_disable.json()["data"]["status"] == CommonEnabledStatus.DISABLED.value
    assert asyncio.run(_count_sellable_card_audits()) == 2

    # disable no-op：不写审计
    r_disable_noop = client.post(
        f"/api/v1/admin/sellable-cards/{sellable_id}/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_disable_noop.status_code == 200
    assert asyncio.run(_count_sellable_card_audits()) == 2

    # enable：写审计 +1
    r_enable = client.post(
        f"/api/v1/admin/sellable-cards/{sellable_id}/enable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_enable.status_code == 200
    assert r_enable.json()["data"]["status"] == CommonEnabledStatus.ENABLED.value
    assert asyncio.run(_count_sellable_card_audits()) == 3

    # PUT no-op：不写审计
    r_update_noop = client.put(
        f"/api/v1/admin/sellable-cards/{sellable_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "c1",
            "servicePackageTemplateId": template_id,
            "regionLevel": "CITY",
            "priceOriginal": 99.9,
            "sort": 1,
        },
    )
    assert r_update_noop.status_code == 200
    assert asyncio.run(_count_sellable_card_audits()) == 3


