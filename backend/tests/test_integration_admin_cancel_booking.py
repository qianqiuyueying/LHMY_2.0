"""集成测试：Admin 强制取消预约（BE-ADMIN-003）。

规格来源：
- specs/health-services-platform/design.md -> E-12. Admin 强制取消预约
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.booking import Booking
from app.models.enums import BookingConfirmationMethod, BookingStatus, CommonEnabledStatus
from app.models.venue_schedule import VenueSchedule
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


def test_admin_cancel_booking_releases_capacity_and_bypasses_window():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    token, _jti = create_admin_token(admin_id=admin_id)

    booking_id = str(uuid4())
    venue_id = str(uuid4())
    service_type = "MASSAGE"
    booking_date = (datetime.now(tz=UTC) + timedelta(hours=1)).date()
    time_slot = "09:00-10:00"

    sched_id = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # 排期：容量=10，剩余=9（表示已占用 1）
            session.add(
                VenueSchedule(
                    id=sched_id,
                    venue_id=venue_id,
                    service_type=service_type,
                    booking_date=booking_date,
                    time_slot=time_slot,
                    capacity=10,
                    remaining_capacity=9,
                    status=CommonEnabledStatus.ENABLED.value,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

            # 预约：CONFIRMED（USER 取消会受 2h 窗口影响，但 Admin 不受）
            session.add(
                Booking(
                    id=booking_id,
                    entitlement_id=str(uuid4()),
                    user_id=str(uuid4()),
                    venue_id=venue_id,
                    service_type=service_type,
                    booking_date=booking_date,
                    time_slot=time_slot,
                    status=BookingStatus.CONFIRMED.value,
                    confirmation_method=BookingConfirmationMethod.AUTO.value,
                    confirmed_at=datetime.utcnow(),
                    cancelled_at=None,
                    cancel_reason=None,
                    created_at=datetime.utcnow(),
                )
            )

            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    r = client.request(
        "DELETE",
        f"/api/v1/admin/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "运营强制取消"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "CANCELLED"
    assert "ADMIN_CANCEL:" in (r.json()["data"]["cancelReason"] or "")

    async def _assert_db() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            b = (await session.get(Booking, booking_id))
            assert b is not None
            assert b.status == BookingStatus.CANCELLED.value
            sched = (await session.get(VenueSchedule, sched_id))
            assert sched is not None
            # 容量释放：9 -> 10
            assert int(sched.remaining_capacity) == 10

    asyncio.run(_assert_db())

