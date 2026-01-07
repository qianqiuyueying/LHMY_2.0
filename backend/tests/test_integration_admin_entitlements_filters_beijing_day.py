"""集成测试：Admin 权益监管（核销/转赠）的 dateFrom/dateTo 北京自然日边界。

规格来源（单一真相来源）：
- specs-prod/admin/api-contracts.md#9O.2/#9O.3（dateFrom/dateTo 按北京时间自然日解释）
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
from app.models.entitlement_transfer import EntitlementTransfer
from app.models.enums import RedemptionMethod, RedemptionStatus
from app.models.redemption_record import RedemptionRecord
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


def test_admin_redemptions_and_transfers_date_filter_beijing_day_boundary():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # 北京时间 2026-01-07 00:00:00 == UTC 2026-01-06 16:00:00
    r_before = str(uuid4())
    r_at = str(uuid4())
    r_inside = str(uuid4())
    t_before = str(uuid4())
    t_at = str(uuid4())
    t_inside = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add_all(
                [
                    RedemptionRecord(
                        id=r_before,
                        entitlement_id=str(uuid4()),
                        booking_id=None,
                        user_id=str(uuid4()),
                        venue_id=str(uuid4()),
                        service_type="SVC:IT",
                        redemption_method=RedemptionMethod.VOUCHER_CODE.value,
                        status=RedemptionStatus.SUCCESS.value,
                        failure_reason=None,
                        operator_id=str(uuid4()),
                        redemption_time=datetime(2026, 1, 6, 15, 59, 59, tzinfo=UTC).replace(tzinfo=None),
                        service_completed_at=None,
                        notes=None,
                    ),
                    RedemptionRecord(
                        id=r_at,
                        entitlement_id=str(uuid4()),
                        booking_id=None,
                        user_id=str(uuid4()),
                        venue_id=str(uuid4()),
                        service_type="SVC:IT",
                        redemption_method=RedemptionMethod.VOUCHER_CODE.value,
                        status=RedemptionStatus.SUCCESS.value,
                        failure_reason=None,
                        operator_id=str(uuid4()),
                        redemption_time=datetime(2026, 1, 6, 16, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                        service_completed_at=None,
                        notes=None,
                    ),
                    RedemptionRecord(
                        id=r_inside,
                        entitlement_id=str(uuid4()),
                        booking_id=None,
                        user_id=str(uuid4()),
                        venue_id=str(uuid4()),
                        service_type="SVC:IT",
                        redemption_method=RedemptionMethod.VOUCHER_CODE.value,
                        status=RedemptionStatus.SUCCESS.value,
                        failure_reason=None,
                        operator_id=str(uuid4()),
                        redemption_time=datetime(2026, 1, 6, 23, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                        service_completed_at=None,
                        notes=None,
                    ),
                    EntitlementTransfer(
                        id=t_before,
                        entitlement_id=str(uuid4()),
                        from_owner_id=str(uuid4()),
                        to_owner_id=str(uuid4()),
                        transferred_at=datetime(2026, 1, 6, 15, 59, 59, tzinfo=UTC).replace(tzinfo=None),
                    ),
                    EntitlementTransfer(
                        id=t_at,
                        entitlement_id=str(uuid4()),
                        from_owner_id=str(uuid4()),
                        to_owner_id=str(uuid4()),
                        transferred_at=datetime(2026, 1, 6, 16, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                    ),
                    EntitlementTransfer(
                        id=t_inside,
                        entitlement_id=str(uuid4()),
                        from_owner_id=str(uuid4()),
                        to_owner_id=str(uuid4()),
                        transferred_at=datetime(2026, 1, 6, 23, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                    ),
                ]
            )
            await session.commit()

    asyncio.run(_seed())

    r = client.get(
        "/api/v1/admin/redemptions",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"dateFrom": "2026-01-07", "dateTo": "2026-01-07", "page": 1, "pageSize": 50},
    )
    assert r.status_code == 200
    ids = {x["id"] for x in (r.json()["data"]["items"] or [])}
    assert r_before not in ids
    assert r_at in ids
    assert r_inside in ids

    t = client.get(
        "/api/v1/admin/entitlement-transfers",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"dateFrom": "2026-01-07", "dateTo": "2026-01-07", "page": 1, "pageSize": 50},
    )
    assert t.status_code == 200
    ids2 = {x["id"] for x in (t.json()["data"]["items"] or [])}
    assert t_before not in ids2
    assert t_at in ids2
    assert t_inside in ids2


