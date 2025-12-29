"""开发/测试辅助接口（admin-dev）。

规格来源：
- specs/功能实现/admin/tasks.md -> B01（演示/测试数据初始化机制）

约束：
- 仅 ADMIN 可访问
- v1 以“固定 ID + reset 可重复执行”实现可复现数据集，便于页面联调与回归
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.api.v1.deps import require_admin
from app.models.after_sale_case import AfterSaleCase
from app.models.booking import Booking
from app.models.entitlement import Entitlement
from app.models.enums import (
    AfterSaleStatus,
    AfterSaleType,
    BookingConfirmationMethod,
    BookingStatus,
    EntitlementStatus,
    EntitlementType,
    OrderType,
    PaymentStatus,
    ProductFulfillmentType,
    ProductStatus,
    NotificationReceiverType,
    NotificationStatus,
)
from app.models.notification import Notification
from app.models.order import Order
from app.models.product import Product
from app.models.provider import Provider
from app.models.user import User
from app.models.venue import Venue
from app.models.venue_service import VenueService
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.settings import settings

router = APIRouter(tags=["admin-dev"])


class SeedDemoDataBody(BaseModel):
    reset: bool = False


DEMO_PROVIDER_ID = "00000000-0000-0000-0000-000000000101"
DEMO_VENUE_ID = "00000000-0000-0000-0000-000000000102"
DEMO_USER_ID = "00000000-0000-0000-0000-000000000103"
DEMO_ORDER_ID = "00000000-0000-0000-0000-000000000104"
DEMO_ORDER_ID_2 = "00000000-0000-0000-0000-000000000304"
DEMO_PRODUCT_ID = "00000000-0000-0000-0000-000000000105"
DEMO_PRODUCT_ID_2 = "00000000-0000-0000-0000-000000000205"
DEMO_ENTITLEMENT_ID = "00000000-0000-0000-0000-000000000106"
DEMO_ENTITLEMENT_ID_2 = "00000000-0000-0000-0000-000000000306"
DEMO_BOOKING_ID = "00000000-0000-0000-0000-000000000107"
DEMO_BOOKING_ID_2 = "00000000-0000-0000-0000-000000000207"
DEMO_AFTER_SALE_ID = "00000000-0000-0000-0000-000000000108"
DEMO_AFTER_SALE_ID_2 = "00000000-0000-0000-0000-000000000208"
DEMO_VENUE_SERVICE_ID = "00000000-0000-0000-0000-000000000109"
DEMO_NOTIFICATION_ID = "00000000-0000-0000-0000-000000000110"
DEMO_NOTIFICATION_ID_2 = "00000000-0000-0000-0000-000000000210"

DEMO_SERVICE_TYPE = "DEMO_SERVICE"
DEMO_VOUCHER_CODE = "DEMO-VOUCHER-0001"
DEMO_VOUCHER_CODE_2 = "DEMO-VOUCHER-0002"


@router.post("/admin/dev/seed")
async def seed_demo_data(
    request: Request,
    body: SeedDemoDataBody,
    _admin=Depends(require_admin),
):
    # 生产环境硬门禁：禁止写入演示数据
    if str(getattr(settings, "app_env", "") or "").strip().lower() == "production":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "生产环境禁止 seed 演示数据"})
    now = datetime.now(tz=UTC)
    booking_day: date = (now + timedelta(days=1)).date()

    session_factory = get_session_factory()
    async with session_factory() as session:
        if body.reset:
            # 以固定 ID 删除，可重复执行
            await session.execute(delete(Notification).where(Notification.id.in_([DEMO_NOTIFICATION_ID, DEMO_NOTIFICATION_ID_2])))
            await session.execute(
                delete(AfterSaleCase).where(AfterSaleCase.id.in_([DEMO_AFTER_SALE_ID, DEMO_AFTER_SALE_ID_2]))
            )
            await session.execute(delete(Booking).where(Booking.id.in_([DEMO_BOOKING_ID, DEMO_BOOKING_ID_2])))
            await session.execute(
                delete(Entitlement).where(Entitlement.id.in_([DEMO_ENTITLEMENT_ID, DEMO_ENTITLEMENT_ID_2]))
            )
            await session.execute(delete(Order).where(Order.id.in_([DEMO_ORDER_ID, DEMO_ORDER_ID_2])))
            await session.execute(delete(Product).where(Product.id.in_([DEMO_PRODUCT_ID, DEMO_PRODUCT_ID_2])))
            await session.execute(delete(VenueService).where(VenueService.id == DEMO_VENUE_SERVICE_ID))
            await session.execute(delete(Venue).where(Venue.id == DEMO_VENUE_ID))
            await session.execute(delete(User).where(User.id == DEMO_USER_ID))
            await session.execute(delete(Provider).where(Provider.id == DEMO_PROVIDER_ID))
            await session.commit()

        # Provider
        provider = (await session.scalars(select(Provider).where(Provider.id == DEMO_PROVIDER_ID).limit(1))).first()
        if provider is None:
            provider = Provider(id=DEMO_PROVIDER_ID, name="DEMO 场所方（Provider）")
            session.add(provider)

        # Venue
        venue = (await session.scalars(select(Venue).where(Venue.id == DEMO_VENUE_ID).limit(1))).first()
        if venue is None:
            venue = Venue(
                id=DEMO_VENUE_ID,
                provider_id=DEMO_PROVIDER_ID,
                name="DEMO 场所（Venue）",
                publish_status="PUBLISHED",
                address="DEMO 地址",
            )
            session.add(venue)

        # VenueService（用于核销校验：场所支持该服务 + 核销方式一致）
        vs = (
            await session.scalars(select(VenueService).where(VenueService.id == DEMO_VENUE_SERVICE_ID).limit(1))
        ).first()
        if vs is None:
            vs = VenueService(
                id=DEMO_VENUE_SERVICE_ID,
                venue_id=DEMO_VENUE_ID,
                service_type=DEMO_SERVICE_TYPE,
                title="DEMO 服务",
                fulfillment_type=ProductFulfillmentType.SERVICE.value,
                product_id=DEMO_PRODUCT_ID,
                booking_required=False,
                redemption_method="VOUCHER_CODE",
                applicable_regions=None,
                status="ENABLED",
            )
            session.add(vs)

        # User
        user = (await session.scalars(select(User).where(User.id == DEMO_USER_ID).limit(1))).first()
        if user is None:
            user = User(id=DEMO_USER_ID, phone="13800000000", nickname="DEMO 用户", identities=["MEMBER"])
            session.add(user)

        # Product（待审核）
        product = (await session.scalars(select(Product).where(Product.id == DEMO_PRODUCT_ID).limit(1))).first()
        if product is None:
            product = Product(
                id=DEMO_PRODUCT_ID,
                provider_id=DEMO_PROVIDER_ID,
                title="DEMO 商品（待审核）",
                fulfillment_type=ProductFulfillmentType.SERVICE.value,
                price={"original": 199.0, "employee": None, "member": None, "activity": None},
                status=ProductStatus.PENDING_REVIEW.value,
                description="用于联调：商品审核/监管的最小演示数据。",
            )
            session.add(product)

        product2 = (await session.scalars(select(Product).where(Product.id == DEMO_PRODUCT_ID_2).limit(1))).first()
        if product2 is None:
            product2 = Product(
                id=DEMO_PRODUCT_ID_2,
                provider_id=DEMO_PROVIDER_ID,
                title="DEMO 商品2（待审核，用于驳回）",
                fulfillment_type=ProductFulfillmentType.SERVICE.value,
                price={"original": 99.0, "employee": None, "member": None, "activity": None},
                status=ProductStatus.PENDING_REVIEW.value,
                description="用于联调：商品审核/监管（驳回流程）演示数据。",
            )
            session.add(product2)

        # Order（用于售后/权益/经销商订单示例）
        order = (await session.scalars(select(Order).where(Order.id == DEMO_ORDER_ID).limit(1))).first()
        if order is None:
            order = Order(
                id=DEMO_ORDER_ID,
                user_id=DEMO_USER_ID,
                order_type=OrderType.SERVICE_PACKAGE.value,
                total_amount=199.0,
                payment_status=PaymentStatus.PAID.value,
                paid_at=now.replace(tzinfo=None),
            )
            session.add(order)

        order2 = (await session.scalars(select(Order).where(Order.id == DEMO_ORDER_ID_2).limit(1))).first()
        if order2 is None:
            order2 = Order(
                id=DEMO_ORDER_ID_2,
                user_id=DEMO_USER_ID,
                order_type=OrderType.SERVICE_PACKAGE.value,
                total_amount=50.0,
                payment_status=PaymentStatus.PAID.value,
                paid_at=now.replace(tzinfo=None),
            )
            session.add(order2)

        # Entitlement（用于“售后同意退款”链路的最小样例）
        ent = (await session.scalars(select(Entitlement).where(Entitlement.id == DEMO_ENTITLEMENT_ID).limit(1))).first()
        if ent is None:
            ent = Entitlement(
                id=DEMO_ENTITLEMENT_ID,
                user_id=DEMO_USER_ID,
                order_id=DEMO_ORDER_ID,
                entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                service_type=DEMO_SERVICE_TYPE,
                remaining_count=1,
                total_count=1,
                valid_from=(now - timedelta(days=1)).replace(tzinfo=None),
                valid_until=(now + timedelta(days=30)).replace(tzinfo=None),
                applicable_venues=[DEMO_VENUE_ID],
                applicable_regions=["CITY:110100"],
                qr_code="DEMO_QR_PAYLOAD_UNUSED",
                voucher_code=DEMO_VOUCHER_CODE,
                status=EntitlementStatus.ACTIVE.value,
                service_package_instance_id=None,
                owner_id=DEMO_USER_ID,
                activator_id="",
                current_user_id="",
            )
            session.add(ent)

        # Entitlement2（用于“核销成功 + 核销记录可查询”的样例；避免被售后退款链路影响）
        ent2 = (
            await session.scalars(select(Entitlement).where(Entitlement.id == DEMO_ENTITLEMENT_ID_2).limit(1))
        ).first()
        if ent2 is None:
            ent2 = Entitlement(
                id=DEMO_ENTITLEMENT_ID_2,
                user_id=DEMO_USER_ID,
                order_id=DEMO_ORDER_ID_2,
                entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                service_type=DEMO_SERVICE_TYPE,
                remaining_count=1,
                total_count=1,
                valid_from=(now - timedelta(days=1)).replace(tzinfo=None),
                valid_until=(now + timedelta(days=30)).replace(tzinfo=None),
                applicable_venues=[DEMO_VENUE_ID],
                applicable_regions=["CITY:110100"],
                qr_code="DEMO_QR_PAYLOAD_UNUSED",
                voucher_code=DEMO_VOUCHER_CODE_2,
                status=EntitlementStatus.ACTIVE.value,
                service_package_instance_id=None,
                owner_id=DEMO_USER_ID,
                activator_id="",
                current_user_id="",
            )
            session.add(ent2)

        # Booking（待确认）
        booking = (await session.scalars(select(Booking).where(Booking.id == DEMO_BOOKING_ID).limit(1))).first()
        if booking is None:
            booking = Booking(
                id=DEMO_BOOKING_ID,
                entitlement_id=DEMO_ENTITLEMENT_ID_2,
                user_id=DEMO_USER_ID,
                venue_id=DEMO_VENUE_ID,
                service_type=DEMO_SERVICE_TYPE,
                booking_date=booking_day,
                time_slot="10:00-11:00",
                status=BookingStatus.PENDING.value,
                confirmation_method=BookingConfirmationMethod.MANUAL.value,
                confirmed_at=None,
                cancelled_at=None,
                cancel_reason=None,
            )
            session.add(booking)

        booking2 = (await session.scalars(select(Booking).where(Booking.id == DEMO_BOOKING_ID_2).limit(1))).first()
        if booking2 is None:
            booking2 = Booking(
                id=DEMO_BOOKING_ID_2,
                entitlement_id=DEMO_ENTITLEMENT_ID_2,
                user_id=DEMO_USER_ID,
                venue_id=DEMO_VENUE_ID,
                service_type=DEMO_SERVICE_TYPE,
                booking_date=booking_day,
                time_slot="14:00-15:00",
                status=BookingStatus.PENDING.value,
                confirmation_method=BookingConfirmationMethod.MANUAL.value,
                confirmed_at=None,
                cancelled_at=None,
                cancel_reason=None,
            )
            session.add(booking2)

        # AfterSale（待裁决）
        as_case = (
            await session.scalars(select(AfterSaleCase).where(AfterSaleCase.id == DEMO_AFTER_SALE_ID).limit(1))
        ).first()
        if as_case is None:
            as_case = AfterSaleCase(
                id=DEMO_AFTER_SALE_ID,
                order_id=DEMO_ORDER_ID,
                user_id=DEMO_USER_ID,
                type=AfterSaleType.REFUND.value,
                status=AfterSaleStatus.UNDER_REVIEW.value,
                amount=199.0,
                reason="DEMO：用户原因申请退款",
                evidence_urls=None,
                decided_by=None,
                decision=None,
                decision_notes=None,
            )
            session.add(as_case)

        as_case2 = (
            await session.scalars(select(AfterSaleCase).where(AfterSaleCase.id == DEMO_AFTER_SALE_ID_2).limit(1))
        ).first()
        if as_case2 is None:
            as_case2 = AfterSaleCase(
                id=DEMO_AFTER_SALE_ID_2,
                order_id=DEMO_ORDER_ID,
                user_id=DEMO_USER_ID,
                type=AfterSaleType.REFUND.value,
                status=AfterSaleStatus.UNDER_REVIEW.value,
                amount=99.0,
                reason="DEMO：用于裁决驳回流程",
                evidence_urls=None,
                decided_by=None,
                decision=None,
                decision_notes=None,
            )
            session.add(as_case2)

        # Notification（用于验证顶栏通知功能可见）
        # v1：仅 ADMIN 自己的站内通知（receiverType=ADMIN, receiverId=adminId）
        admin_id = str(getattr(_admin, "sub", "") or "")
        if admin_id:
            n1 = (
                await session.scalars(select(Notification).where(Notification.id == DEMO_NOTIFICATION_ID).limit(1))
            ).first()
            if n1 is None:
                session.add(
                    Notification(
                        id=DEMO_NOTIFICATION_ID,
                        receiver_type=NotificationReceiverType.ADMIN.value,
                        receiver_id=admin_id,
                        title="演示通知：你有待处理事项",
                        content="这是演示数据：用于验证“通知抽屉”可拉取/可标记已读。",
                        status=NotificationStatus.UNREAD.value,
                    )
                )

            n2 = (
                await session.scalars(select(Notification).where(Notification.id == DEMO_NOTIFICATION_ID_2).limit(1))
            ).first()
            if n2 is None:
                session.add(
                    Notification(
                        id=DEMO_NOTIFICATION_ID_2,
                        receiver_type=NotificationReceiverType.ADMIN.value,
                        receiver_id=admin_id,
                        title="演示通知：配置发布提醒",
                        content="建议：发布小程序配置后，去小程序端验证入口/页面/集合是否可用。",
                        status=NotificationStatus.UNREAD.value,
                    )
                )

        await session.commit()

    return ok(
        data={
            "seeded": True,
            "ids": {
                "providerId": DEMO_PROVIDER_ID,
                "venueId": DEMO_VENUE_ID,
                "venueServiceId": DEMO_VENUE_SERVICE_ID,
                "userId": DEMO_USER_ID,
                "orderId": DEMO_ORDER_ID,
                "orderId2": DEMO_ORDER_ID_2,
                "productId": DEMO_PRODUCT_ID,
                "productId2": DEMO_PRODUCT_ID_2,
                "entitlementId": DEMO_ENTITLEMENT_ID,
                "entitlementId2": DEMO_ENTITLEMENT_ID_2,
                "voucherCode2": DEMO_VOUCHER_CODE_2,
                "bookingId": DEMO_BOOKING_ID,
                "bookingId2": DEMO_BOOKING_ID_2,
                "afterSaleId": DEMO_AFTER_SALE_ID,
                "afterSaleId2": DEMO_AFTER_SALE_ID_2,
            },
        },
        request_id=request.state.request_id,
    )

