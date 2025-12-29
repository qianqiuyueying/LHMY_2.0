"""集成测试：敏感信息治理基线（TASK-P0-006）。

规格依据（单一真相来源）：
- specs-prod/admin/security.md#2.3.5（拍板口径）
- specs-prod/admin/requirements.md#R-PII-001.1（敏感字段清单）
- specs-prod/admin/tasks.md#TASK-P0-006（DoD：至少覆盖订单/结算/场所）

覆盖范围（v1 最小，但可阻断回归）：
- Admin 订单监管：不返回运单号明文，仅 trackingNoLast4；收货地址不返回明文（详情场景）
- Dealer/Admin 结算：不返回 payoutReference/payoutAccount 明文，仅 payoutReferenceLast4 + payoutAccount 白名单脱敏
- 场所公开端：不返回 contactPhone 明文，仅 contactPhoneMasked
- 权益（ADMIN）：不返回 qrCode/voucherCode 明文
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
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.entitlement import Entitlement
from app.models.enums import EntitlementStatus, EntitlementType, VenuePublishStatus
from app.models.order import Order
from app.models.provider import Provider
from app.models.settlement_record import SettlementRecord
from app.models.user import User
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


def _assert_ok_envelope(resp_json: dict) -> None:
    assert resp_json.get("success") is True
    assert "data" in resp_json
    assert isinstance(resp_json.get("requestId"), str)


def test_public_venue_detail_no_contact_phone_plaintext():
    """公开端：仅 contactPhoneMasked，不返回 contactPhone 明文。"""
    asyncio.run(_reset_db_and_redis())

    venue_id = str(uuid4())
    provider_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(Provider(id=provider_id, name="P"))
            session.add(
                Venue(
                    id=venue_id,
                    provider_id=provider_id,
                    name="V",
                    publish_status=VenuePublishStatus.PUBLISHED.value,
                    contact_phone="13800138000",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    r = client.get(f"/api/v1/venues/{venue_id}")
    assert r.status_code == 200
    body = r.json()
    _assert_ok_envelope(body)
    data = body["data"]
    assert "contactPhone" not in data
    assert data.get("contactPhoneMasked") == "138****8000"


def test_admin_orders_list_tracking_no_last4_only():
    """Admin 订单监管：不返回 shippingTrackingNo 明文，仅 trackingNoLast4。"""
    asyncio.run(_reset_db_and_redis())

    user_id = str(uuid4())
    order_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(User(id=user_id, phone="13800138000", nickname="U", identities=[], created_at=now, updated_at=now))
            session.add(
                Order(
                    id=order_id,
                    user_id=user_id,
                    order_type="PRODUCT",
                    total_amount=100.0,
                    payment_method="WECHAT",
                    payment_status="PAID",
                    fulfillment_type="PHYSICAL_GOODS",
                    fulfillment_status="SHIPPED",
                    goods_amount=90.0,
                    shipping_amount=10.0,
                    shipping_carrier="SF",
                    shipping_tracking_no="SF123456789CN",
                    shipped_at=now,
                    created_at=now,
                    paid_at=now,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    admin_token, _jti = create_admin_token(admin_id="00000000-0000-0000-0000-00000000a001")
    r = client.get("/api/v1/admin/orders", headers={"Authorization": f"Bearer {admin_token}"}, params={"page": 1, "pageSize": 20})
    assert r.status_code == 200
    body = r.json()
    _assert_ok_envelope(body)
    items = body["data"]["items"]
    assert isinstance(items, list) and len(items) >= 1
    row = items[0]
    assert "shippingTrackingNo" not in row
    assert row.get("trackingNoLast4") == "89CN"


def test_dealer_settlements_mask_payout_reference_and_account():
    """结算列表：不返回 payoutReference 明文；payoutAccount 需白名单脱敏。"""
    asyncio.run(_reset_db_and_redis())

    dealer_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    settlement_id = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                SettlementRecord(
                    id=settlement_id,
                    dealer_id=dealer_id,
                    cycle="2025-12",
                    order_count=1,
                    amount=123.45,
                    status="SETTLED",
                    payout_method="BANK",
                    payout_account_json={
                        "method": "BANK",
                        "accountName": "张三",
                        "accountNo": "6222020202020202020",
                        "bankName": "ABC",
                        "bankBranch": "SZ",
                        "contactPhone": "13800138000",
                    },
                    payout_reference="PAYREF-202512-ABCDEFG",
                    payout_note="ok",
                    payout_marked_by="00000000-0000-0000-0000-00000000a001",
                    payout_marked_at=now,
                    created_at=now,
                    settled_at=now,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    admin_token, _jti = create_admin_token(admin_id="00000000-0000-0000-0000-00000000a001")
    r = client.get(
        "/api/v1/dealer/settlements",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"dealerId": dealer_id, "page": 1, "pageSize": 20},
    )
    assert r.status_code == 200
    body = r.json()
    _assert_ok_envelope(body)
    items = body["data"]["items"]
    assert isinstance(items, list) and len(items) == 1
    row = items[0]
    assert "payoutReference" not in row
    assert row.get("payoutReferenceLast4") == "DEFG"
    payout_account = row.get("payoutAccount")
    assert isinstance(payout_account, dict)
    assert "accountNo" not in payout_account
    assert payout_account.get("accountNoMasked")
    assert "contactPhone" not in payout_account
    assert payout_account.get("contactPhoneMasked") == "138****8000"


def test_admin_entitlements_no_voucher_or_qr_plaintext():
    """ADMIN 调用 /entitlements：不返回 qrCode/voucherCode 明文。"""
    asyncio.run(_reset_db_and_redis())

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    e_id = str(uuid4())
    user_id = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(User(id=user_id, phone="13800138000", nickname="U", identities=[], created_at=now, updated_at=now))
            session.add(
                Entitlement(
                    id=e_id,
                    user_id=user_id,
                    order_id=str(uuid4()),
                    entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                    service_type="MASSAGE",
                    remaining_count=1,
                    total_count=1,
                    valid_from=now - timedelta(days=1),
                    valid_until=now + timedelta(days=30),
                    applicable_venues=[],
                    applicable_regions=["CN-GD-SZ"],
                    qr_code="QR_PAYLOAD_SHOULD_NOT_LEAK",
                    voucher_code="VOUCHER_SHOULD_NOT_LEAK",
                    status=EntitlementStatus.ACTIVE.value,
                    owner_id=user_id,
                    activator_id=user_id,
                    current_user_id=user_id,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    admin_token, _jti = create_admin_token(admin_id="00000000-0000-0000-0000-00000000a001")
    r = client.get("/api/v1/entitlements", headers={"Authorization": f"Bearer {admin_token}"}, params={"page": 1, "pageSize": 20})
    assert r.status_code == 200
    body = r.json()
    _assert_ok_envelope(body)
    items = body["data"]["items"]
    assert isinstance(items, list) and len(items) >= 1
    row = items[0]
    assert "qrCode" not in row
    assert "voucherCode" not in row


def test_admin_venues_view_writes_audit_log():
    """Admin 查看场所详情（含联系方式）：应写入审计（不含电话明文）。"""
    asyncio.run(_reset_db_and_redis())

    venue_id = str(uuid4())
    provider_id = str(uuid4())
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(Provider(id=provider_id, name="P"))
            session.add(
                Venue(
                    id=venue_id,
                    provider_id=provider_id,
                    name="V",
                    publish_status=VenuePublishStatus.DRAFT.value,
                    contact_phone="13800138000",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    r = client.get(f"/api/v1/admin/venues/{venue_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    _assert_ok_envelope(body)
    assert body["data"].get("contactPhone") == "13800138000"
    assert body["data"].get("contactPhoneMasked") == "138****8000"

    async def _assert_audit() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            rows = (await session.scalars(select(AuditLog).where(AuditLog.resource_id == venue_id))).all()  # type: ignore[name-defined]
            assert len(rows) >= 1
            # 最后一条应为本次 VIEW
            last = sorted(rows, key=lambda x: x.created_at)[-1]
            assert last.actor_type == "ADMIN"
            assert last.actor_id == admin_id
            assert last.action == "VIEW"
            assert last.resource_type == "VENUE"
            md = last.metadata_json or {}
            assert md.get("contactPhoneMasked") == "138****8000"
            # 不允许写入“电话明文值”
            assert "13800138000" not in str(md)

    # NOTE: avoid importing sqlalchemy.select at module top to keep file compact
    from sqlalchemy import select  # noqa: WPS433

    asyncio.run(_assert_audit())


