"""集成测试：Admin 经销商结算（资金高风险）审计 + 幂等口径证明。

规格来源（本仓新规格，单一真相来源）：
- specs-prod/admin/api-contracts.md#5-Admin-Dealer-Settlements（经销商结算 - 高风险）
- specs-prod/admin/api-contracts.md#1.4 状态机写操作的统一口径（幂等 no-op / 409）
- specs-prod/admin/tasks.md#FLOW-DEALER-SETTLEMENTS
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
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.dealer import Dealer
from app.models.enums import DealerStatus, OrderType, PaymentStatus, SettlementStatus
from app.models.order import Order
from app.models.settlement_record import SettlementRecord
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token
from app.utils.redis_client import get_redis
from sqlalchemy import func, select

pytestmark = pytest.mark.skipif(os.getenv("RUN_INTEGRATION_TESTS") != "1", reason="integration tests disabled")


async def _reset_db_and_redis() -> None:
    r = get_redis()
    await r.flushdb()

    session_factory = get_session_factory()
    async with session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


async def _seed_settlement(*, status: str) -> str:
    sid = str(uuid4())
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            SettlementRecord(
                id=sid,
                dealer_id=str(uuid4()),
                cycle="2025-12",
                order_count=1,
                amount=12.34,
                status=status,
                payout_method=None,
                payout_account_json=None,
                payout_reference=None,
                payout_note=None,
                payout_marked_by=None,
                payout_marked_at=None,
                created_at=datetime.now(tz=UTC).replace(tzinfo=None),
                settled_at=None,
            )
        )
        await session.commit()
    return sid


def test_admin_dealer_settlement_mark_settled_idempotent_and_audited():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    settlement_id = asyncio.run(_seed_settlement(status=SettlementStatus.PENDING_CONFIRM.value))

    # 1) 首次标记：PENDING_CONFIRM -> SETTLED（200）+ 审计入库
    r1 = client.post(
        f"/api/v1/admin/dealer-settlements/{settlement_id}/mark-settled",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"payoutReference": "BANK-REF-00001234", "payoutNote": "it note"},
    )
    assert r1.status_code == 200
    assert r1.json()["success"] is True
    assert r1.json()["data"]["status"] == SettlementStatus.SETTLED.value
    assert r1.json()["data"]["payoutReference"] == "BANK-REF-00001234"

    # 查审计：必须能按 resourceType/resourceId 找到至少 1 条，且包含 before/after
    r_audit = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"resourceType": "DEALER_SETTLEMENT", "resourceId": settlement_id, "page": 1, "pageSize": 50},
    )
    assert r_audit.status_code == 200
    items = r_audit.json()["data"]["items"]
    assert isinstance(items, list)
    assert len(items) >= 1
    # 找到我们这条业务审计（metadata 有 beforeStatus/afterStatus）
    assert any(
        (x.get("metadata") or {}).get("beforeStatus") == SettlementStatus.PENDING_CONFIRM.value
        and (x.get("metadata") or {}).get("afterStatus") == SettlementStatus.SETTLED.value
        for x in items
    )

    # 2) 重复标记：同目标状态重复提交 => 200 幂等 no-op，且不得覆盖首次写入的 payoutReference
    r2 = client.post(
        f"/api/v1/admin/dealer-settlements/{settlement_id}/mark-settled",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"payoutReference": "BANK-REF-OVERWRITE-XXXX", "payoutNote": "should_not_overwrite"},
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert r2.json()["data"]["status"] == SettlementStatus.SETTLED.value
    assert r2.json()["data"]["payoutReference"] == "BANK-REF-00001234"

    # 3) 幂等 no-op 不应额外写入业务审计（避免刷屏）
    async def _count_business_audit() -> int:
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(func.count()).select_from(AuditLog).where(
                AuditLog.resource_type == "DEALER_SETTLEMENT",
                AuditLog.resource_id == settlement_id,
            )
            return int((await session.execute(stmt)).scalar() or 0)

    # 至少 1 条；并且重复提交不会额外新增（容忍 middleware 的通用审计存在，但业务审计应保持 1 条）
    assert asyncio.run(_count_business_audit()) == 1


def test_admin_dealer_settlement_mark_settled_frozen_409():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    settlement_id = asyncio.run(_seed_settlement(status=SettlementStatus.FROZEN.value))
    r = client.post(
        f"/api/v1/admin/dealer-settlements/{settlement_id}/mark-settled",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"payoutReference": "BANK-REF-00001234"},
    )
    assert r.status_code == 409
    payload = r.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "STATE_CONFLICT"


def test_admin_dealer_settlement_generate_idempotent_and_audited():
    asyncio.run(_reset_db_and_redis())

    admin_id = "00000000-0000-0000-0000-00000000a001"
    admin_token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    cycle = "2025-12"
    dealer_id = str(uuid4())

    async def _seed_dealer_and_paid_order() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Dealer(
                    id=dealer_id,
                    name="IT Dealer",
                    level=None,
                    parent_dealer_id=None,
                    status=DealerStatus.ACTIVE.value,
                    contact_name=None,
                    contact_phone=None,
                    created_at=datetime.now(tz=UTC).replace(tzinfo=None),
                    updated_at=datetime.now(tz=UTC).replace(tzinfo=None),
                )
            )
            session.add(
                Order(
                    id=str(uuid4()),
                    user_id=str(uuid4()),
                    order_type=OrderType.SERVICE_PACKAGE.value,
                    total_amount=100.0,
                    payment_method="WECHAT",
                    payment_status=PaymentStatus.PAID.value,
                    dealer_id=dealer_id,
                    dealer_link_id=None,
                    fulfillment_type=None,
                    fulfillment_status=None,
                    goods_amount=0.0,
                    shipping_amount=0.0,
                    shipping_address_json=None,
                    reservation_expires_at=None,
                    shipping_carrier=None,
                    shipping_tracking_no=None,
                    shipped_at=None,
                    delivered_at=None,
                    received_at=None,
                    created_at=datetime.now(tz=UTC).replace(tzinfo=None),
                    paid_at=datetime(2025, 12, 5, 12, 0, 0),
                    confirmed_at=None,
                )
            )
            await session.commit()

    asyncio.run(_seed_dealer_and_paid_order())

    # 1) 首次 generate：应创建 1 条结算单（created>=1）
    r1 = client.post(
        "/api/v1/admin/dealer-settlements/generate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"cycle": cycle},
    )
    assert r1.status_code == 200
    assert r1.json()["success"] is True
    assert r1.json()["data"]["cycle"] == cycle
    assert r1.json()["data"]["created"] >= 1

    # 2) 同 cycle 重复 generate：幂等，不重复创建（created==0，existing>=1）
    r2 = client.post(
        "/api/v1/admin/dealer-settlements/generate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"cycle": cycle},
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is True
    assert r2.json()["data"]["created"] == 0
    assert r2.json()["data"]["existing"] >= 1

    # 3) 审计：至少能查到 generate 的业务审计（resourceType=DEALER_SETTLEMENT_BATCH, resourceId=cycle）
    r_audit = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"resourceType": "DEALER_SETTLEMENT_BATCH", "resourceId": cycle, "page": 1, "pageSize": 50},
    )
    assert r_audit.status_code == 200
    assert r_audit.json()["data"]["total"] >= 1

