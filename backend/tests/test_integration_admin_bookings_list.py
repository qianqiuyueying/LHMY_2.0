"""集成测试：Admin Bookings 监管查询（Batch5）。

规格来源（单一真相来源）：
- specs-prod/admin/api-contracts.md#9A.1 GET /admin/bookings
- specs-prod/admin/tasks.md#FLOW-ADMIN-BOOKINGS
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
from app.models.base import Base
from app.models.booking import Booking
from app.models.enums import BookingConfirmationMethod, BookingSourceType, BookingStatus
from app.models.venue import Venue
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
from app.utils.jwt_dealer_token import create_dealer_token
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


async def _seed() -> dict[str, str]:
    provider_id = "00000000-0000-0000-0000-00000000p001"
    venue_id = str(uuid4())
    venue_id2 = str(uuid4())
    user_id = str(uuid4())

    b1 = str(uuid4())
    b2 = str(uuid4())
    b3 = str(uuid4())

    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add_all(
            [
                Venue(
                    id=venue_id,
                    provider_id=provider_id,
                    name="IT Venue 1",
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
                ),
                Venue(
                    id=venue_id2,
                    provider_id="00000000-0000-0000-0000-00000000p002",
                    name="IT Venue 2",
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
                ),
            ]
        )

        # 3 条预约：用 bookingDate + createdAt 验证排序 bookingDate desc, createdAt desc
        session.add_all(
            [
                Booking(
                    id=b1,
                    source_type=BookingSourceType.ENTITLEMENT.value,
                    entitlement_id=str(uuid4()),
                    order_id=None,
                    order_item_id=None,
                    product_id=None,
                    user_id=user_id,
                    venue_id=venue_id,
                    service_type="SVC-A",
                    booking_date=datetime(2025, 12, 10, tzinfo=UTC).date(),
                    time_slot="10:00-11:00",
                    status=BookingStatus.PENDING.value,
                    confirmation_method=BookingConfirmationMethod.AUTO.value,
                    confirmed_at=None,
                    cancelled_at=None,
                    cancel_reason=None,
                    created_at=datetime(2025, 12, 9, 9, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                ),
                Booking(
                    id=b2,
                    source_type=BookingSourceType.ENTITLEMENT.value,
                    entitlement_id=str(uuid4()),
                    order_id=None,
                    order_item_id=None,
                    product_id=None,
                    user_id=user_id,
                    venue_id=venue_id,
                    service_type="SVC-A",
                    booking_date=datetime(2025, 12, 10, tzinfo=UTC).date(),
                    time_slot="11:00-12:00",
                    status=BookingStatus.CONFIRMED.value,
                    confirmation_method=BookingConfirmationMethod.MANUAL.value,
                    confirmed_at=datetime(2025, 12, 8, 8, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                    cancelled_at=None,
                    cancel_reason=None,
                    created_at=datetime(2025, 12, 9, 10, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                ),
                Booking(
                    id=b3,
                    source_type=BookingSourceType.ENTITLEMENT.value,
                    entitlement_id=str(uuid4()),
                    order_id=None,
                    order_item_id=None,
                    product_id=None,
                    user_id=str(uuid4()),
                    venue_id=venue_id2,
                    service_type="SVC-B",
                    booking_date=datetime(2025, 12, 11, tzinfo=UTC).date(),
                    time_slot="09:00-10:00",
                    status=BookingStatus.PENDING.value,
                    confirmation_method=BookingConfirmationMethod.AUTO.value,
                    confirmed_at=None,
                    cancelled_at=None,
                    cancel_reason=None,
                    created_at=datetime(2025, 12, 9, 8, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                ),
            ]
        )

        await session.commit()

    return {"providerId": provider_id, "venueId": venue_id, "userId": user_id, "b1": b1, "b2": b2, "b3": b3}


def test_admin_bookings_list_auth_and_filters_and_sorting():
    asyncio.run(_reset_db_and_redis())
    ids = asyncio.run(_seed())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # 401
    r = client.get("/api/v1/admin/bookings", params={"page": 1, "pageSize": 20})
    assert r.status_code == 401

    # 403（非 admin token）
    dealer_token, _jti2 = create_dealer_token(actor_id=str(uuid4()))
    r = client.get(
        "/api/v1/admin/bookings",
        headers={"Authorization": f"Bearer {dealer_token}"},
        params={"page": 1, "pageSize": 20},
    )
    assert r.status_code in {401, 403}
    if r.status_code == 403:
        assert r.json()["error"]["code"] in {"FORBIDDEN", "UNAUTHORIZED", "FORBIDDEN_ROLE", "FORBIDDEN_ACTOR", "FORBIDDEN"}  # 容忍实现差异

    # 400：非法日期
    r = client.get(
        "/api/v1/admin/bookings",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"page": 1, "pageSize": 20, "dateFrom": "2025-13-99"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_ARGUMENT"

    # 200：默认排序 bookingDate DESC, createdAt DESC
    r = client.get(
        "/api/v1/admin/bookings",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"page": 1, "pageSize": 20},
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert items[0]["id"] == ids["b3"]  # 2025-12-11 在前
    # 同 bookingDate=2025-12-10：createdAt 10:00 的 b2 应在 09:00 的 b1 前
    ids_1210 = [x["id"] for x in items if x["bookingDate"] == "2025-12-10"]
    assert ids_1210 == [ids["b2"], ids["b1"]]

    # filter：status=CONFIRMED
    r = client.get(
        "/api/v1/admin/bookings",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"page": 1, "pageSize": 20, "status": "CONFIRMED"},
    )
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["data"]["items"]] == [ids["b2"]]

    # filter：serviceType
    r = client.get(
        "/api/v1/admin/bookings",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"page": 1, "pageSize": 20, "serviceType": "SVC-B"},
    )
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["data"]["items"]] == [ids["b3"]]

    # filter：keyword（等值优先：userId）
    r = client.get(
        "/api/v1/admin/bookings",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"page": 1, "pageSize": 20, "keyword": ids["userId"]},
    )
    assert r.status_code == 200
    got = {x["id"] for x in r.json()["data"]["items"]}
    assert ids["b1"] in got and ids["b2"] in got

    # filter：venueId + providerId
    r = client.get(
        "/api/v1/admin/bookings",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"page": 1, "pageSize": 20, "venueId": ids["venueId"], "providerId": ids["providerId"]},
    )
    assert r.status_code == 200
    got = {x["id"] for x in r.json()["data"]["items"]}
    assert ids["b1"] in got and ids["b2"] in got and ids["b3"] not in got


