"""集成测试：Admin 核销记录列表（BE-ADMIN-004）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-004

说明：
- 需要 MySQL/Redis，因此仅在 RUN_INTEGRATION_TESTS=1 时运行。
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
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


def test_admin_redemptions_list_filters():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    token, _jti = create_admin_token(admin_id=admin_id)

    now = datetime.utcnow()
    r1_id = str(uuid4())
    r2_id = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                RedemptionRecord(
                    id=r1_id,
                    entitlement_id=str(uuid4()),
                    booking_id=None,
                    user_id=str(uuid4()),
                    venue_id=str(uuid4()),
                    service_type="MASSAGE",
                    redemption_method=RedemptionMethod.QR_CODE.value,
                    status=RedemptionStatus.SUCCESS.value,
                    failure_reason=None,
                    operator_id=admin_id,
                    redemption_time=now - timedelta(days=1),
                    service_completed_at=now - timedelta(days=1),
                    notes=None,
                )
            )
            session.add(
                RedemptionRecord(
                    id=r2_id,
                    entitlement_id=str(uuid4()),
                    booking_id=None,
                    user_id=str(uuid4()),
                    venue_id=str(uuid4()),
                    service_type="SWIM",
                    redemption_method=RedemptionMethod.VOUCHER_CODE.value,
                    status=RedemptionStatus.FAILED.value,
                    failure_reason="x",
                    operator_id=str(uuid4()),
                    redemption_time=now,
                    service_completed_at=None,
                    notes=None,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)

    # 1) serviceType filter
    resp = client.get(
        "/api/v1/admin/redemptions?serviceType=MASSAGE",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    ids = [x["id"] for x in resp.json()["data"]["items"]]
    assert r1_id in ids
    assert r2_id not in ids

    # 2) operatorId filter
    resp2 = client.get(
        f"/api/v1/admin/redemptions?operatorId={admin_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    items2 = resp2.json()["data"]["items"]
    assert len(items2) == 1
    assert items2[0]["id"] == r1_id
