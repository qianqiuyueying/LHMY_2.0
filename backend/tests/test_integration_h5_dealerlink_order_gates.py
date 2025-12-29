"""集成测试：H5 服务包下单 dealerLinkId 门禁（最高门禁）。

规格来源：
- specs/health-services-platform/tasks.md -> REQ-H5-P1-005（dealerLinkId 作为长期投放入口 + 最高门禁）

断言（最小）：
- SERVICE_PACKAGE 下单必须带 dealerLinkId（缺失返回 400）
- dealerLinkId 不存在返回 404
- dealerLinkId 未绑定 sellableCardId 返回 400
- dealerLinkId 被停用返回 403
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
from app.models.base import Base
from app.models.dealer import Dealer
from app.models.dealer_link import DealerLink
from app.models.enums import CommonEnabledStatus, DealerLinkStatus, DealerStatus
from app.models.package_service import PackageService
from app.models.sellable_card import SellableCard
from app.models.service_package import ServicePackage
from app.models.user import User
from app.utils.db import get_session_factory
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


def test_h5_service_package_order_requires_dealer_link_id_and_valid_link():
    asyncio.run(_reset_db_and_redis())

    user_id = str(uuid4())
    dealer_id = str(uuid4())
    sellable_card_id = str(uuid4())
    sp_template_id = str(uuid4())
    pkg_service_id = str(uuid4())

    entry_link_id = str(uuid4())
    authorized_card_link_id = str(uuid4())
    disabled_link_id = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(User(id=user_id, phone="13900000001", openid=None, unionid=None, nickname="u", avatar=None, identities=[]))
            session.add(Dealer(id=dealer_id, name="D1", level=None, parent_dealer_id=None, status=DealerStatus.ACTIVE.value))

            session.add(ServicePackage(id=sp_template_id, name="市卡", region_level="CITY", tier="T1", description=None))
            session.add(PackageService(id=pkg_service_id, service_package_id=sp_template_id, service_type="MASSAGE", total_count=1))

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

            # 指定卡链接（可用）
            session.add(
                DealerLink(
                    id=authorized_card_link_id,
                    dealer_id=dealer_id,
                    product_id=None,
                    sellable_card_id=sellable_card_id,
                    campaign="gate",
                    status=DealerLinkStatus.ENABLED.value,
                    valid_from=None,
                    valid_until=(datetime.now(tz=UTC) + timedelta(days=1)).replace(tzinfo=None),
                    url=f"/h5?dealerLinkId={enabled_card_link_id}",
                    uv=None,
                    paid_count=None,
                )
            )

            # 经销商入口链接（未绑定卡）
            session.add(
                DealerLink(
                    id=entry_link_id,
                    dealer_id=dealer_id,
                    product_id=None,
                    sellable_card_id=None,
                    campaign="gate",
                    status=DealerLinkStatus.ENABLED.value,
                    valid_from=None,
                    valid_until=(datetime.now(tz=UTC) + timedelta(days=1)).replace(tzinfo=None),
                    url=f"/h5?dealerLinkId={home_link_id}",
                    uv=None,
                    paid_count=None,
                )
            )

            # 停用链接
            session.add(
                DealerLink(
                    id=disabled_link_id,
                    dealer_id=dealer_id,
                    product_id=None,
                    sellable_card_id=sellable_card_id,
                    campaign="gate",
                    status=DealerLinkStatus.DISABLED.value,
                    valid_from=None,
                    valid_until=(datetime.now(tz=UTC) + timedelta(days=1)).replace(tzinfo=None),
                    url=f"/h5?dealerLinkId={disabled_link_id}",
                    uv=None,
                    paid_count=None,
                )
            )

            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)
    token = create_user_token(user_id=user_id, channel="H5")

    body = {
        "orderType": "SERVICE_PACKAGE",
        "items": [
            {
                "itemType": "SERVICE_PACKAGE",
                "itemId": sellable_card_id,
                "quantity": 1,
                "servicePackageTemplateId": sp_template_id,
                "regionScope": "CITY:110100",
            }
        ],
    }

    # 1) 缺少 dealerLinkId -> 400
    r0 = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex},
        json=body,
    )
    assert r0.status_code == 400

    # 2) dealerLinkId 不存在 -> 404
    r1 = client.post(
        "/api/v1/orders",
        params={"dealerLinkId": str(uuid4())},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex},
        json=body,
    )
    assert r1.status_code == 404

    # 3) 缺少“卡授权链接”，即使有入口链接也应拒绝（403）
    #    先删掉授权链接：通过使用一个不存在授权的 dealer（这里不方便删库，改为直接把 itemId 改成另一个 sellableCardId）
    other_sellable = str(uuid4())
    body_other = {
        "orderType": "SERVICE_PACKAGE",
        "items": [
            {
                "itemType": "SERVICE_PACKAGE",
                "itemId": other_sellable,
                "quantity": 1,
                "servicePackageTemplateId": sp_template_id,
                "regionScope": "CITY:110100",
            }
        ],
    }
    r2 = client.post(
        "/api/v1/orders",
        params={"dealerLinkId": entry_link_id},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex},
        json=body_other,
    )
    assert r2.status_code == 403

    # 4) 停用链接 -> 403
    r3 = client.post(
        "/api/v1/orders",
        params={"dealerLinkId": disabled_link_id},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex},
        json=body,
    )
    assert r3.status_code == 403

    # 5) 可用链接 -> 200
    r4 = client.post(
        "/api/v1/orders",
        params={"dealerLinkId": entry_link_id},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex},
        json=body,
    )
    assert r4.status_code == 200
    assert r4.json()["data"]["dealerId"] == dealer_id

