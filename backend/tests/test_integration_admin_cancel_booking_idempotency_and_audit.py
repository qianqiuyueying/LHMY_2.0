"""集成测试：Admin 强制取消预约（幂等 + 审计，Batch6）。

规格来源（单一真相来源）：
- specs-prod/admin/api-contracts.md#9A.2 DELETE /admin/bookings/{id}
- specs-prod/admin/api-contracts.md#1.4 状态机写操作统一口径（200 no-op / 409）
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
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.booking import Booking
from app.models.enums import BookingConfirmationMethod, BookingSourceType, BookingStatus
from app.models.venue import Venue
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


async def _seed_booking(*, status: str) -> tuple[str, str]:
    venue_id = str(uuid4())
    booking_id = str(uuid4())
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Venue(
                id=venue_id,
                provider_id=str(uuid4()),
                name="IT Venue",
                logo_url=None,
                cover_image_url=None,
                image_urls=None,
                description=None,
                country_code=None,
                province_code=None,
                city_code=None,
                address=None,
                lat=None,
                lng=None,
                contact_phone=None,
                business_hours=None,
                tags=None,
                publish_status="PUBLISHED",
                created_at=datetime.now(tz=UTC).replace(tzinfo=None),
                updated_at=datetime.now(tz=UTC).replace(tzinfo=None),
            )
        )
        session.add(
            Booking(
                id=booking_id,
                source_type=BookingSourceType.ENTITLEMENT.value,
                entitlement_id=str(uuid4()),
                order_id=None,
                order_item_id=None,
                product_id=None,
                user_id=str(uuid4()),
                venue_id=venue_id,
                service_type="SVC-A",
                booking_date=datetime(2025, 12, 10, tzinfo=UTC).date(),
                time_slot="10:00-11:00",
                status=status,
                confirmation_method=BookingConfirmationMethod.AUTO.value,
                confirmed_at=None,
                cancelled_at=None,
                cancel_reason=None,
                created_at=datetime.now(tz=UTC).replace(tzinfo=None),
            )
        )
        await session.commit()
    return booking_id, venue_id


def test_admin_cancel_booking_requires_idempotency_key_and_is_idempotent_and_audited_once():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    booking_id, _venue_id = asyncio.run(_seed_booking(status=BookingStatus.PENDING.value))

    # 缺 Idempotency-Key -> 400
    r0 = client.request(
        "DELETE",
        f"/api/v1/admin/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "it"},
    )
    assert r0.status_code == 400
    assert r0.json()["error"]["code"] == "INVALID_ARGUMENT"

    idem = "it:admin-cancel:1"

    # 首次取消：200 + CANCELLED
    r1 = client.request(
        "DELETE",
        f"/api/v1/admin/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": idem},
        json={"reason": "it reason"},
    )
    assert r1.status_code == 200
    assert r1.json()["success"] is True
    assert r1.json()["data"]["status"] == BookingStatus.CANCELLED.value

    # 重复提交（同 Idempotency-Key）：200 复放
    r2 = client.request(
        "DELETE",
        f"/api/v1/admin/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": idem},
        json={"reason": "it reason (dup)"},
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert r2.json()["data"]["status"] == BookingStatus.CANCELLED.value

    # 重复提交（不同 Idempotency-Key）：200 no-op（已 CANCELLED）
    r3 = client.request(
        "DELETE",
        f"/api/v1/admin/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "it:admin-cancel:2"},
        json={"reason": "another"},
    )
    assert r3.status_code == 200
    assert r3.json()["success"] is True
    assert r3.json()["data"]["status"] == BookingStatus.CANCELLED.value

    # 业务审计只写一次：resourceType=BOOKING, resourceId=bookingId
    async def _count_booking_audit() -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(func.count()).select_from(AuditLog).where(
                AuditLog.resource_type == "BOOKING", AuditLog.resource_id == booking_id
            )
            return int((await session.execute(stmt)).scalar() or 0)

    assert asyncio.run(_count_booking_audit()) == 1


def test_admin_cancel_booking_completed_is_invalid_transition_409():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    booking_id, _venue_id = asyncio.run(_seed_booking(status=BookingStatus.COMPLETED.value))

    r = client.request(
        "DELETE",
        f"/api/v1/admin/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "it:admin-cancel:3"},
        json={"reason": "it"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


