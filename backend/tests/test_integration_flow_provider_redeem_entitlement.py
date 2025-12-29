"""集成测试：FLOW-PROVIDER-REDEEM（核销：幂等 + 审计 + 响应字段）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9K（你已拍板：必须审计；错误码 v1 保持现状；成功响应含 remainingCount+entitlementStatus；幂等复放不重复写审计）
- specs-prod/admin/tasks.md#FLOW-PROVIDER-REDEEM
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.models  # noqa: F401
from app.main import app
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.entitlement import Entitlement
from app.models.enums import CommonEnabledStatus, EntitlementStatus, EntitlementType, RedemptionMethod
from app.models.venue import Venue
from app.models.venue_service import VenueService
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


async def _seed_venue_and_service(*, venue_id: str, provider_id: str, service_type: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Venue(
                id=venue_id,
                provider_id=provider_id,
                name="IT Venue",
                logo_url=None,
                cover_image_url=None,
                image_urls=None,
                description=None,
                country_code="COUNTRY:CN",
                province_code="PROVINCE:110000",
                city_code="CITY:110100",
                address="addr",
                lat=None,
                lng=None,
                contact_phone=None,
                business_hours=None,
                tags=None,
                publish_status="PUBLISHED",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        session.add(
            VenueService(
                id=str(uuid4()),
                venue_id=venue_id,
                service_type=service_type,
                title="IT Service",
                fulfillment_type="SERVICE",
                product_id=None,
                booking_required=False,
                redemption_method=RedemptionMethod.VOUCHER_CODE.value,
                applicable_regions=None,
                status=CommonEnabledStatus.ENABLED.value,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        await session.commit()


async def _seed_entitlement(*, entitlement_id: str, owner_id: str, order_id: str, service_type: str, voucher_code: str) -> None:
    now = datetime.now(tz=UTC)
    vf = (now - timedelta(days=1)).replace(tzinfo=None)
    vu = (now + timedelta(days=30)).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Entitlement(
                id=entitlement_id,
                user_id=owner_id,
                owner_id=owner_id,
                order_id=order_id,
                entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                service_type=service_type,
                remaining_count=2,
                total_count=2,
                valid_from=vf,
                valid_until=vu,
                applicable_venues=None,
                applicable_regions=None,
                qr_code="qr",
                voucher_code=voucher_code,
                status=EntitlementStatus.ACTIVE.value,
                service_package_instance_id=None,
                activator_id="",
                current_user_id="",
                created_at=datetime.utcnow(),
            )
        )
        await session.commit()


async def _count_audits_for_entitlement_redeem(*, entitlement_id: str) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        n = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.resource_type == "ENTITLEMENT_REDEEM")
                    .where(AuditLog.resource_id == entitlement_id)
                )
            ).scalar()
            or 0
        )
        return n


def test_redeem_entitlement_writes_audit_and_idempotency_replay_does_not_duplicate_audit_and_returns_remaining():
    asyncio.run(_reset_db_and_redis())
    client = TestClient(app)

    admin_id = str(uuid4())
    token, _ = create_admin_token(admin_id=admin_id)

    venue_id = str(uuid4())
    provider_id = str(uuid4())
    service_type = "SVC:IT"
    entitlement_id = str(uuid4())
    owner_id = str(uuid4())
    order_id = str(uuid4())
    voucher_code = "VOUCHER123"

    asyncio.run(_seed_venue_and_service(venue_id=venue_id, provider_id=provider_id, service_type=service_type))
    asyncio.run(
        _seed_entitlement(
            entitlement_id=entitlement_id,
            owner_id=owner_id,
            order_id=order_id,
            service_type=service_type,
            voucher_code=voucher_code,
        )
    )

    # 第一次核销
    r1 = client.post(
        f"/api/v1/entitlements/{entitlement_id}/redeem",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-1"},
        json={"venueId": venue_id, "redemptionMethod": "VOUCHER_CODE", "voucherCode": voucher_code},
    )
    assert r1.status_code == 200
    data1 = r1.json()["data"]
    assert data1["entitlementId"] == entitlement_id
    assert data1["status"] == "SUCCESS"
    assert data1["remainingCount"] == 1
    assert data1["entitlementStatus"] == "ACTIVE"
    assert asyncio.run(_count_audits_for_entitlement_redeem(entitlement_id=entitlement_id)) == 1

    # 同 key 重放：200 幂等复放，不重复写审计
    r2 = client.post(
        f"/api/v1/entitlements/{entitlement_id}/redeem",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-1"},
        json={"venueId": venue_id, "redemptionMethod": "VOUCHER_CODE", "voucherCode": voucher_code},
    )
    assert r2.status_code == 200
    data2 = r2.json()["data"]
    assert data2["redemptionRecordId"] == data1["redemptionRecordId"]
    assert data2["remainingCount"] == 1
    assert asyncio.run(_count_audits_for_entitlement_redeem(entitlement_id=entitlement_id)) == 1


