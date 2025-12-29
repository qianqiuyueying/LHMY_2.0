"""集成测试：Admin 仪表盘统计（BE-ADMIN-001）。

规格来源：
- specs/health-services-platform/design.md -> E-11. Admin 仪表盘统计（v1 最小契约）
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.models.after_sale_case import AfterSaleCase
from app.models.base import Base
from app.models.enums import (
    AfterSaleStatus,
    CommonEnabledStatus,
    OrderType,
    PaymentStatus,
    RedemptionMethod,
    RedemptionStatus,
    UserEnterpriseBindingStatus,
)
from app.models.enterprise import Enterprise
from app.models.enums import EnterpriseSource
from app.models.order import Order
from app.models.redemption_record import RedemptionRecord
from app.models.service_package_instance import ServicePackageInstance
from app.models.system_config import SystemConfig
from app.models.user import User
from app.models.user_enterprise_binding import UserEnterpriseBinding
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


def test_admin_dashboard_summary_counts_and_trends():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    token, _jti = create_admin_token(admin_id=admin_id)

    now = datetime.now(tz=UTC)
    today_paid = now
    yesterday_paid = now - timedelta(days=1)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # 订单：服务包/电商
            session.add_all(
                [
                    Order(
                        id=str(uuid4()),
                        user_id=str(uuid4()),
                        order_type=OrderType.SERVICE_PACKAGE.value,
                        total_amount=100.0,
                        payment_method="WECHAT",
                        payment_status=PaymentStatus.PAID.value,
                        dealer_id=None,
                        created_at=now,
                        paid_at=today_paid,
                        confirmed_at=None,
                    ),
                    Order(
                        id=str(uuid4()),
                        user_id=str(uuid4()),
                        order_type=OrderType.PRODUCT.value,
                        total_amount=50.0,
                        payment_method="WECHAT",
                        payment_status=PaymentStatus.PAID.value,
                        dealer_id=None,
                        created_at=now,
                        paid_at=yesterday_paid,
                        confirmed_at=None,
                    ),
                    Order(
                        id=str(uuid4()),
                        user_id=str(uuid4()),
                        order_type=OrderType.PRODUCT.value,
                        total_amount=50.0,
                        payment_method="WECHAT",
                        payment_status=PaymentStatus.FAILED.value,
                        dealer_id=None,
                        created_at=now,
                        paid_at=None,
                        confirmed_at=None,
                    ),
                ]
            )

            # 售后：退款待审核
            session.add(
                AfterSaleCase(
                    id=str(uuid4()),
                    order_id=str(uuid4()),
                    user_id=str(uuid4()),
                    type="REFUND",
                    status=AfterSaleStatus.UNDER_REVIEW.value,
                    amount=10.0,
                    reason="r",
                    evidence_urls=None,
                    decided_by=None,
                    decision=None,
                    decision_notes=None,
                    created_at=now,
                    updated_at=now,
                )
            )

            # 核销：成功
            session.add(
                RedemptionRecord(
                    id=str(uuid4()),
                    entitlement_id=str(uuid4()),
                    booking_id=None,
                    user_id=str(uuid4()),
                    venue_id=str(uuid4()),
                    service_type="MASSAGE",
                    redemption_method=RedemptionMethod.QR_CODE.value,
                    status=RedemptionStatus.SUCCESS.value,
                    failure_reason=None,
                    operator_id=admin_id,
                    redemption_time=now,
                    service_completed_at=now,
                    notes=None,
                )
            )

            # 新增会员：service_package_instances 去重 owner
            owner_id = str(uuid4())
            session.add_all(
                [
                    ServicePackageInstance(
                        id=str(uuid4()),
                        order_id=str(uuid4()),
                        order_item_id=str(uuid4()),
                        service_package_template_id=str(uuid4()),
                        owner_id=owner_id,
                        region_scope="CITY:110100",
                        tier="T1",
                        valid_from=now,
                        valid_until=now + timedelta(days=365),
                        status="ACTIVE",
                        created_at=now,
                        updated_at=now,
                    ),
                    ServicePackageInstance(
                        id=str(uuid4()),
                        order_id=str(uuid4()),
                        order_item_id=str(uuid4()),
                        service_package_template_id=str(uuid4()),
                        owner_id=owner_id,
                        region_scope="CITY:110100",
                        tier="T1",
                        valid_from=now,
                        valid_until=now + timedelta(days=365),
                        status="ACTIVE",
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )

            # 企业绑定待处理
            binding_user_id = str(uuid4())
            session.add(
                User(
                    id=binding_user_id,
                    phone="13800000000",
                    openid=None,
                    unionid=None,
                    nickname="u",
                    avatar=None,
                    identities=["MEMBER"],
                    enterprise_id=None,
                    enterprise_name=None,
                    binding_time=None,
                    created_at=now.replace(tzinfo=None),
                    updated_at=now.replace(tzinfo=None),
                )
            )
            enterprise_id = str(uuid4())
            session.add(
                Enterprise(
                    id=enterprise_id,
                    name="测试企业",
                    country_code="COUNTRY:CN",
                    province_code="PROVINCE:110000",
                    city_code="CITY:110100",
                    source=EnterpriseSource.USER_FIRST_BINDING.value,
                    first_seen_at=now.replace(tzinfo=None),
                    created_at=now.replace(tzinfo=None),
                    updated_at=now.replace(tzinfo=None),
                )
            )
            session.add(
                UserEnterpriseBinding(
                    id=str(uuid4()),
                    user_id=binding_user_id,
                    enterprise_id=enterprise_id,
                    status=UserEnterpriseBindingStatus.PENDING.value,
                    binding_time=now,
                    created_at=now,
                    updated_at=now,
                )
            )

            # 额外放一条 SystemConfig（保证 SystemConfig 表存在且可清理）
            session.add(
                SystemConfig(
                    id=str(uuid4()),
                    key="DUMMY",
                    value_json={},
                    description="d",
                    status=CommonEnabledStatus.ENABLED.value,
                    created_at=now.replace(tzinfo=None),
                    updated_at=now.replace(tzinfo=None),
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    r = client.get("/api/v1/admin/dashboard/summary?range=7d", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()["data"]

    assert data["range"] == "7d"
    assert data["today"]["servicePackagePaidCount"] == 1
    assert data["today"]["refundUnderReviewCount"] == 1
    assert data["today"]["redemptionSuccessCount"] == 1
    assert data["today"]["newMemberCount"] == 1  # owner 去重

    assert data["todo"]["refundUnderReviewCount"] == 1
    assert data["todo"]["abnormalOrderCount"] == 1
    assert data["todo"]["enterpriseBindingPendingCount"] == 1

    assert len(data["trends"]["servicePackagePaid"]) == 7
    assert len(data["trends"]["ecommercePaid"]) == 7
    assert len(data["trends"]["redemptionSuccess"]) == 7

