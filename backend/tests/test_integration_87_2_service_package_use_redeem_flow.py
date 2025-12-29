"""端到端集成测试：健行天下购买→权益使用→核销流程（阶段17-87.2）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段17-87.2
- specs/health-services-platform/design.md -> H5 端创建 SERVICE_PACKAGE 订单（仅 H5 允许）
- specs/health-services-platform/design.md -> 支付成功生成 ServicePackageInstance + Entitlement（属性7/21/22）
- specs/health-services-platform/design.md -> 预约/确认/核销规则（属性16/17）

测试目标（v1 最小）：
- H5 创建服务包订单并发起支付
- 模拟支付成功回调（生成服务包实例与权益）
- USER 创建预约（MANUAL 模式 -> PENDING）
- ADMIN 确认预约
- ADMIN 通过二维码 payload 核销权益（成功扣次数，预约置为 COMPLETED）
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.booking import Booking
from app.models.dealer import Dealer
from app.models.dealer_link import DealerLink
from app.models.enums import (
    BookingStatus,
    CommonEnabledStatus,
    DealerLinkStatus,
    DealerStatus,
    PaymentStatus,
    ProductFulfillmentType,
    ProductStatus,
    RedemptionMethod,
    VenuePublishStatus,
)
from app.models.order import Order
from app.models.payment import Payment
from app.models.package_service import PackageService
from app.models.provider import Provider
from app.models.sellable_card import SellableCard
from app.models.service_package import ServicePackage
from app.models.system_config import SystemConfig
from app.models.user import User
from app.models.venue import Venue
from app.models.venue_schedule import VenueSchedule
from app.models.venue_service import VenueService
from app.services.payment_callbacks import mark_payment_succeeded
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
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


def test_stage17_87_2_service_package_to_booking_to_redeem_flow():
    asyncio.run(_reset_db_and_redis())

    user_id = str(uuid4())
    admin_id = str(uuid4())

    provider_id = str(uuid4())
    dealer_id = str(uuid4())
    entry_link_id = str(uuid4())
    sellable_card_id = str(uuid4())

    sp_template_id = str(uuid4())
    pkg_service_id = str(uuid4())
    service_type = "MASSAGE"
    region_scope = "CITY:110100"
    tier = "T1"

    venue_id = str(uuid4())
    venue_service_id = str(uuid4())
    schedule_id = str(uuid4())

    booking_date = date.today() + timedelta(days=1)
    time_slot = "09:00-10:00"

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                User(
                    id=user_id, phone="13900000000", openid=None, unionid=None, nickname="u", avatar=None, identities=[]
                )
            )
            session.add(Provider(id=provider_id, name="P1"))
            session.add(Dealer(id=dealer_id, name="D1", level=None, parent_dealer_id=None, status=DealerStatus.ACTIVE.value))

            # 服务包模板与“服务类目×次数”
            session.add(
                ServicePackage(id=sp_template_id, name="市卡", region_level="CITY", tier=tier, description=None)
            )
            session.add(
                PackageService(
                    id=pkg_service_id, service_package_id=sp_template_id, service_type=service_type, total_count=2
                )
            )

            # 可售卡（v2.1：SERVICE_PACKAGE 下单计价载体）
            session.add(
                SellableCard(
                    id=sellable_card_id,
                    name="市卡（测试）",
                    product_id=None,
                    service_package_template_id=sp_template_id,
                    region_level="CITY",
                    region_scope=None,
                    tier=None,
                    price_original=1999,
                    status=CommonEnabledStatus.ENABLED.value,
                    sort=0,
                )
            )

            # 经销商投放链接（指定卡购卡链接）
            # 经销商入口链接（用于 H5 购买入口身份）
            session.add(
                DealerLink(
                    id=entry_link_id,
                    dealer_id=dealer_id,
                    product_id=None,
                    sellable_card_id=None,
                    campaign="stage17-entry",
                    status=DealerLinkStatus.ENABLED.value,
                    valid_from=None,
                    valid_until=None,
                    url=f"/h5?dealerLinkId={entry_link_id}",
                    uv=None,
                    paid_count=None,
                )
            )
            # 卡授权链接（表示该经销商可售卖该卡）
            session.add(
                DealerLink(
                    id=str(uuid4()),
                    dealer_id=dealer_id,
                    product_id=None,
                    sellable_card_id=sellable_card_id,
                    campaign="stage17-card",
                    status=DealerLinkStatus.ENABLED.value,
                    valid_from=None,
                    valid_until=None,
                    url=f"/h5?dealerLinkId={entry_link_id}&sellableCardId={sellable_card_id}",
                    uv=None,
                    paid_count=None,
                )
            )

            # 预约确认模式：MANUAL
            session.add(
                SystemConfig(
                    id=str(uuid4()),
                    key="BOOKING_CONFIRMATION_METHOD",
                    value_json={"method": "MANUAL"},
                    description="stage17 integration test",
                    status=CommonEnabledStatus.ENABLED.value,
                )
            )

            # 场所与服务（需要预约，核销方式：QR_CODE）
            session.add(
                Venue(
                    id=venue_id,
                    provider_id=provider_id,
                    name="V1",
                    logo_url=None,
                    cover_image_url=None,
                    image_urls=None,
                    description=None,
                    country_code="COUNTRY:CN",
                    province_code="PROVINCE:110000",
                    city_code="CITY:110100",
                    address=None,
                    lat=None,
                    lng=None,
                    contact_phone=None,
                    business_hours=None,
                    tags=None,
                    publish_status=VenuePublishStatus.PUBLISHED.value,
                )
            )
            session.add(
                VenueService(
                    id=venue_service_id,
                    venue_id=venue_id,
                    service_type=service_type,
                    title="按摩",
                    fulfillment_type=ProductFulfillmentType.SERVICE.value,
                    product_id=None,
                    booking_required=True,
                    redemption_method=RedemptionMethod.QR_CODE.value,
                    applicable_regions=[region_scope],
                    status=CommonEnabledStatus.ENABLED.value,
                )
            )
            session.add(
                VenueSchedule(
                    id=schedule_id,
                    venue_id=venue_id,
                    service_type=service_type,
                    booking_date=booking_date,
                    time_slot=time_slot,
                    capacity=5,
                    remaining_capacity=5,
                    status=CommonEnabledStatus.ENABLED.value,
                )
            )

            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    user_token_h5 = create_user_token(user_id=user_id, channel="H5")
    user_token_mp = create_user_token(user_id=user_id, channel="MINI_PROGRAM")
    admin_token, _jti = create_admin_token(admin_id=admin_id)

    # 1) H5 创建服务包订单
    r1 = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {user_token_h5}", "Idempotency-Key": uuid4().hex},
        params={"dealerLinkId": entry_link_id},
        json={
            "orderType": "SERVICE_PACKAGE",
            "items": [
                {
                    "itemType": "SERVICE_PACKAGE",
                    "itemId": sellable_card_id,
                    "quantity": 1,
                    "servicePackageTemplateId": sp_template_id,
                    "regionScope": region_scope,
                    "tier": tier,
                }
            ],
        },
    )
    assert r1.status_code == 200
    order_id = r1.json()["data"]["id"]

    # 2) 发起支付（创建 payment 记录）
    r2 = client.post(
        f"/api/v1/orders/{order_id}/pay",
        headers={"Authorization": f"Bearer {user_token_h5}", "Idempotency-Key": uuid4().hex},
        json={"paymentMethod": "WECHAT"},
    )
    assert r2.status_code == 200

    async def _simulate_pay_success() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            o = (await session.scalars(select(Order).where(Order.id == order_id).limit(1))).first()
            assert o is not None
            assert o.payment_status == PaymentStatus.PENDING.value

            p = (await session.scalars(select(Payment).where(Payment.order_id == order_id).limit(1))).first()
            assert p is not None
            await mark_payment_succeeded(
                session=session, order_id=order_id, payment_id=p.id, provider_payload={"mock": True}
            )

    asyncio.run(_simulate_pay_success())

    # 3) USER 查询权益，取出一条服务包权益
    r3 = client.get(
        "/api/v1/entitlements", headers={"Authorization": f"Bearer {user_token_mp}"}, params={"type": "SERVICE_PACKAGE"}
    )
    assert r3.status_code == 200
    entitlements = r3.json()["data"]["items"]
    assert entitlements
    e0 = entitlements[0]
    assert e0["entitlementType"] == "SERVICE_PACKAGE"
    assert e0["serviceType"] == service_type
    assert e0["status"] == "ACTIVE"

    entitlement_id = e0["id"]
    qr_payload_text = e0["qrCode"]

    # 4) USER 创建预约（MANUAL -> PENDING）
    r4 = client.post(
        "/api/v1/bookings",
        headers={"Authorization": f"Bearer {user_token_mp}", "Idempotency-Key": uuid4().hex},
        json={
            "entitlementId": entitlement_id,
            "venueId": venue_id,
            "bookingDate": booking_date.strftime("%Y-%m-%d"),
            "timeSlot": time_slot,
        },
    )
    assert r4.status_code == 200
    booking_id = r4.json()["data"]["id"]
    assert r4.json()["data"]["status"] == BookingStatus.PENDING.value

    # 5) ADMIN 确认预约
    r5 = client.put(
        f"/api/v1/bookings/{booking_id}/confirm",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": uuid4().hex},
    )
    assert r5.status_code == 200
    assert r5.json()["data"]["status"] == BookingStatus.CONFIRMED.value

    # 6) ADMIN 核销（二维码核销，需传完整 payload 文本）
    r6 = client.post(
        f"/api/v1/entitlements/{entitlement_id}/redeem",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": uuid4().hex},
        json={"venueId": venue_id, "redemptionMethod": "QR_CODE", "voucherCode": qr_payload_text},
    )
    assert r6.status_code == 200
    assert r6.json()["data"]["status"] == "SUCCESS"

    # 7) 断言：预约派生为 COMPLETED
    async def _assert_booking_completed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            b = (await session.scalars(select(Booking).where(Booking.id == booking_id).limit(1))).first()
            assert b is not None
            assert b.status == BookingStatus.COMPLETED.value

    asyncio.run(_assert_booking_completed())
