"""集成测试：用户侧权益链路的时间/日期语义（样板：validUntil vs activatedAt/usedAt）。

规格来源（单一真相来源）：
- specs/health-services-platform/time-and-timezone.md（timestamp vs business date）
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.entitlement import Entitlement
from app.models.enums import EntitlementStatus, EntitlementType, RedemptionMethod, RedemptionStatus
from app.models.redemption_record import RedemptionRecord
from app.utils.db import get_session_factory
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


def test_user_entitlements_business_dates_and_timestamp_fields():
    asyncio.run(_reset_db_and_redis())

    user_id = str(uuid4())
    token = create_user_token(user_id=user_id, channel="MINI_PROGRAM")
    client = TestClient(app)

    ent_active = str(uuid4())
    ent_used = str(uuid4())

    # 固定时间：便于断言
    first_redeem = datetime(2026, 1, 8, 1, 2, 3, tzinfo=UTC)
    last_redeem = datetime(2026, 1, 9, 4, 5, 6, tzinfo=UTC)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add_all(
                [
                    Entitlement(
                        id=ent_active,
                        user_id=user_id,
                        owner_id=user_id,
                        order_id=str(uuid4()),
                        entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                        service_type="SVC:IT",
                        remaining_count=1,
                        total_count=2,
                        # business date semantics: store as datetime but output as YYYY-MM-DD
                        valid_from=datetime(2026, 1, 7, 0, 0, 0),
                        valid_until=datetime(2026, 1, 31, 0, 0, 0),
                        applicable_venues=None,
                        applicable_regions=None,
                        qr_code="qr",
                        voucher_code="VOUCHER1",
                        status=EntitlementStatus.ACTIVE.value,
                        service_package_instance_id=None,
                        activator_id="",
                        current_user_id="",
                        created_at=datetime(2026, 1, 7, 12, 0, 0),
                    ),
                    Entitlement(
                        id=ent_used,
                        user_id=user_id,
                        owner_id=user_id,
                        order_id=str(uuid4()),
                        entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                        service_type="SVC:IT",
                        remaining_count=0,
                        total_count=1,
                        valid_from=datetime(2026, 1, 1, 0, 0, 0),
                        valid_until=datetime(2026, 1, 31, 0, 0, 0),
                        applicable_venues=None,
                        applicable_regions=None,
                        qr_code="qr",
                        voucher_code="VOUCHER2",
                        status=EntitlementStatus.USED.value,
                        service_package_instance_id=None,
                        activator_id="",
                        current_user_id="",
                        created_at=datetime(2026, 1, 1, 12, 0, 0),
                    ),
                    # redemption history
                    RedemptionRecord(
                        id=str(uuid4()),
                        entitlement_id=ent_active,
                        booking_id=None,
                        user_id=user_id,
                        venue_id=str(uuid4()),
                        service_type="SVC:IT",
                        redemption_method=RedemptionMethod.VOUCHER_CODE.value,
                        status=RedemptionStatus.SUCCESS.value,
                        failure_reason=None,
                        operator_id=str(uuid4()),
                        redemption_time=first_redeem,
                        service_completed_at=first_redeem,
                        notes=None,
                    ),
                    RedemptionRecord(
                        id=str(uuid4()),
                        entitlement_id=ent_used,
                        booking_id=None,
                        user_id=user_id,
                        venue_id=str(uuid4()),
                        service_type="SVC:IT",
                        redemption_method=RedemptionMethod.VOUCHER_CODE.value,
                        status=RedemptionStatus.SUCCESS.value,
                        failure_reason=None,
                        operator_id=str(uuid4()),
                        redemption_time=last_redeem,
                        service_completed_at=last_redeem,
                        notes=None,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(_seed())

    r = client.get("/api/v1/entitlements", headers={"Authorization": f"Bearer {token}"}, params={"page": 1, "pageSize": 50})
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    by_id = {x["id"]: x for x in items}

    a = by_id[ent_active]
    assert a["validFrom"] == "2026-01-07"
    assert a["validUntil"] == "2026-01-31"
    assert a["createdAt"].endswith("Z")
    assert a["activatedAt"].endswith("Z")
    assert a["usedAt"] is None

    u = by_id[ent_used]
    assert u["validUntil"] == "2026-01-31"
    assert u["activatedAt"].endswith("Z")
    assert u["usedAt"].endswith("Z")

    r2 = client.get(f"/api/v1/entitlements/{ent_used}", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    d = r2.json()["data"]
    assert d["validUntil"] == "2026-01-31"
    assert d["usedAt"].endswith("Z")


