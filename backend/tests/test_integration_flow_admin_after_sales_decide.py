"""集成测试：FLOW-ADMIN-AFTER-SALES（售后审核 decide：phone bound + 幂等 + 审计 + 错误码）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9N（phone bound、200 no-op、409 INVALID_STATE_TRANSITION、审计 action=UPDATE、保留 REFUND_NOT_ALLOWED）
- specs-prod/admin/tasks.md#FLOW-ADMIN-AFTER-SALES
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
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.entitlement import Entitlement
from app.models.enums import EntitlementStatus, EntitlementType, OrderType, PaymentStatus, RedemptionMethod, RedemptionStatus
from app.models.order import Order
from app.models.redemption_record import RedemptionRecord
from app.models.user import User
from app.services.password_hashing import hash_password
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


async def _seed_admin(*, admin_id: str, phone: str | None) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Admin(
                id=admin_id,
                username=f"it_admin_after_sales_{admin_id[-4:]}",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone=phone,
            )
        )
        await session.commit()


async def _count_after_sales_audit(*, after_sale_id: str) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        n = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.resource_type == "AFTER_SALES")
                    .where(AuditLog.resource_id == after_sale_id)
                    .where(AuditLog.action == "UPDATE")
                )
            ).scalar()
            or 0
        )
        return n


def test_admin_after_sales_decide_requires_phone_bound_and_is_idempotent_and_audited():
    asyncio.run(_reset_db_and_redis())

    user_id = str(uuid4())
    order_id = str(uuid4())
    entitlement_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    admin_unbound_id = str(uuid4())
    admin_bound_id = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_unbound_id, phone=None))
    asyncio.run(_seed_admin(admin_id=admin_bound_id, phone="13800138000"))

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(User(id=user_id, phone="13600000000", nickname="u", identities=[]))
            session.add(
                Order(
                    id=order_id,
                    user_id=user_id,
                    order_type=OrderType.SERVICE_PACKAGE.value,
                    total_amount=99.0,
                    payment_status=PaymentStatus.PAID.value,
                    paid_at=now,
                )
            )
            session.add(
                Entitlement(
                    id=entitlement_id,
                    user_id=user_id,
                    order_id=order_id,
                    entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                    service_type="DEMO_SERVICE",
                    remaining_count=1,
                    total_count=1,
                    valid_from=now - timedelta(days=1),
                    valid_until=now + timedelta(days=30),
                    applicable_venues=None,
                    applicable_regions=["CITY:110100"],
                    qr_code="DEMO_QR_PAYLOAD",
                    voucher_code="DEMO-VOUCHER-REFUND-1",
                    status=EntitlementStatus.ACTIVE.value,
                    service_package_instance_id=None,
                    owner_id=user_id,
                    activator_id="",
                    current_user_id="",
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    user_token = create_user_token(user_id=user_id, channel="MINI_PROGRAM")
    unbound_token, _ = create_admin_token(admin_id=admin_unbound_id)
    bound_token, _ = create_admin_token(admin_id=admin_bound_id)

    # 1) USER 创建售后（自动进入 UNDER_REVIEW）
    r1 = client.post(
        "/api/v1/after-sales",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"orderId": order_id, "type": "REFUND", "reason": "不想要了"},
    )
    assert r1.status_code == 200
    after_sale_id = r1.json()["data"]["id"]
    assert r1.json()["data"]["status"] == "UNDER_REVIEW"

    # 2) 未绑定手机号 -> 403 ADMIN_PHONE_REQUIRED
    r_forbidden = client.put(
        f"/api/v1/admin/after-sales/{after_sale_id}/decide",
        headers={"Authorization": f"Bearer {unbound_token}"},
        json={"decision": "REJECT", "decisionNotes": "no"},
    )
    assert r_forbidden.status_code == 403
    assert r_forbidden.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # 3) 绑定手机号 -> 200，写业务审计 AFTER_SALES(UPDATE)
    r_ok = client.put(
        f"/api/v1/admin/after-sales/{after_sale_id}/decide",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"decision": "REJECT", "decisionNotes": "reject"},
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["data"]["status"] == "CLOSED"
    assert r_ok.json()["data"]["decision"] == "REJECT"
    assert asyncio.run(_count_after_sales_audit(after_sale_id=after_sale_id)) == 1

    # 4) 重复同一决策 -> 200 no-op，不重复写业务审计
    r_noop = client.put(
        f"/api/v1/admin/after-sales/{after_sale_id}/decide",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"decision": "REJECT", "decisionNotes": "ignore"},
    )
    assert r_noop.status_code == 200
    assert r_noop.json()["data"]["status"] == "CLOSED"
    assert r_noop.json()["data"]["decision"] == "REJECT"
    assert asyncio.run(_count_after_sales_audit(after_sale_id=after_sale_id)) == 1

    # 5) 冲突决策 -> 409 INVALID_STATE_TRANSITION
    r_conflict = client.put(
        f"/api/v1/admin/after-sales/{after_sale_id}/decide",
        headers={"Authorization": f"Bearer {bound_token}"},
        json={"decision": "APPROVE", "decisionNotes": "conflict"},
    )
    assert r_conflict.status_code == 409
    assert r_conflict.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_admin_after_sales_approve_refund_not_allowed_keeps_refund_not_allowed_code():
    asyncio.run(_reset_db_and_redis())

    user_id = str(uuid4())
    admin_id = str(uuid4())
    order_id = str(uuid4())
    entitlement_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    asyncio.run(_seed_admin(admin_id=admin_id, phone="13800138000"))

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(User(id=user_id, phone="13600000000", nickname="u", identities=[]))
            session.add(
                Order(
                    id=order_id,
                    user_id=user_id,
                    order_type=OrderType.SERVICE_PACKAGE.value,
                    total_amount=99.0,
                    payment_status=PaymentStatus.PAID.value,
                    paid_at=now,
                )
            )
            session.add(
                Entitlement(
                    id=entitlement_id,
                    user_id=user_id,
                    order_id=order_id,
                    entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                    service_type="DEMO_SERVICE",
                    remaining_count=1,
                    total_count=1,
                    valid_from=now - timedelta(days=1),
                    valid_until=now + timedelta(days=30),
                    applicable_venues=None,
                    applicable_regions=["CITY:110100"],
                    qr_code="DEMO_QR_PAYLOAD",
                    voucher_code="DEMO-VOUCHER-REFUND-1",
                    status=EntitlementStatus.ACTIVE.value,
                    service_package_instance_id=None,
                    owner_id=user_id,
                    activator_id="",
                    current_user_id="",
                )
            )
            # seed a SUCCESS redemption -> refund rule should reject with REFUND_NOT_ALLOWED
            session.add(
                RedemptionRecord(
                    id=str(uuid4()),
                    entitlement_id=entitlement_id,
                    booking_id=None,
                    user_id=user_id,
                    venue_id=str(uuid4()),
                    service_type="DEMO_SERVICE",
                    redemption_method=RedemptionMethod.VOUCHER_CODE.value,
                    status=RedemptionStatus.SUCCESS.value,
                    failure_reason=None,
                    operator_id=str(uuid4()),
                    redemption_time=datetime.now(tz=UTC),
                    service_completed_at=None,
                    notes=None,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    user_token = create_user_token(user_id=user_id, channel="MINI_PROGRAM")
    admin_token, _ = create_admin_token(admin_id=admin_id)

    # create after-sales
    r1 = client.post(
        "/api/v1/after-sales",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"orderId": order_id, "type": "REFUND", "reason": "不想要了"},
    )
    assert r1.status_code == 200
    after_sale_id = r1.json()["data"]["id"]
    assert r1.json()["data"]["status"] == "UNDER_REVIEW"

    # approve should be rejected by refund rule -> 409 REFUND_NOT_ALLOWED（保持现状，不收敛）
    r2 = client.put(
        f"/api/v1/admin/after-sales/{after_sale_id}/decide",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "APPROVE", "decisionNotes": "approve"},
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "REFUND_NOT_ALLOWED"


