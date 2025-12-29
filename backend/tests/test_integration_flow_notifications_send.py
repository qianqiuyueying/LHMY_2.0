"""集成测试：FLOW-NOTIFICATIONS-SEND（通知发送：phone bound + Idempotency-Key + 限流 + targetsCount 上限）。

规格依据（单一真相来源）：
- specs-prod/admin/api-contracts.md#9J
- specs-prod/admin/tasks.md#FLOW-NOTIFICATIONS-SEND
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.models  # noqa: F401
from app.main import app
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.notification import Notification
from app.services.password_hashing import hash_password
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


async def _seed_admin(*, admin_id: str, phone: str | None) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            Admin(
                id=admin_id,
                username=f"it_admin_notif_{admin_id[-4:]}",
                password_hash=hash_password(password="Abcdef!2345"),
                status="ACTIVE",
                phone=phone,
            )
        )
        await session.commit()


async def _count_notifications() -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        n = int((await session.execute(select(func.count()).select_from(Notification))).scalar() or 0)
        return n


async def _count_send_audits() -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        n = int(
            (
                await session.execute(
                    select(func.count()).select_from(AuditLog).where(AuditLog.resource_type == "NOTIFICATION_SEND")
                )
            ).scalar()
            or 0
        )
        return n


def test_notifications_send_guards_and_idempotency_and_rate_limit():
    asyncio.run(_reset_db_and_redis())

    admin_unbound = str(uuid4())
    admin_bound = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_unbound, phone=None))
    asyncio.run(_seed_admin(admin_id=admin_bound, phone="13800138000"))

    token_unbound, _ = create_admin_token(admin_id=admin_unbound)
    token_bound, _ = create_admin_token(admin_id=admin_bound)

    client = TestClient(app)

    body_target_self = {
        "title": "t",
        "content": "c",
        "category": "SYSTEM",
        "audience": {"mode": "TARGETED", "targets": [{"receiverType": "ADMIN", "receiverId": admin_bound}]},
    }

    # 1) 缺少 Idempotency-Key -> 400 INVALID_ARGUMENT
    r_missing = client.post("/api/v1/admin/notifications/send", headers={"Authorization": f"Bearer {token_bound}"}, json=body_target_self)
    assert r_missing.status_code == 400
    assert r_missing.json()["error"]["code"] == "INVALID_ARGUMENT"

    # 2) 未绑定手机号 -> 403 ADMIN_PHONE_REQUIRED
    r_phone = client.post(
        "/api/v1/admin/notifications/send",
        headers={"Authorization": f"Bearer {token_unbound}", "Idempotency-Key": "k-1"},
        json=body_target_self,
    )
    assert r_phone.status_code == 403
    assert r_phone.json()["error"]["code"] == "ADMIN_PHONE_REQUIRED"

    # 3) targetsCount > 5000（TARGETED）-> 400 INVALID_ARGUMENT（在 resolve 前拒绝）
    too_many = [{"receiverType": "ADMIN", "receiverId": "x"} for _ in range(5001)]
    r_oversize = client.post(
        "/api/v1/admin/notifications/send",
        headers={"Authorization": f"Bearer {token_bound}", "Idempotency-Key": "k-oversize"},
        json={"title": "t", "content": "c", "category": "SYSTEM", "audience": {"mode": "TARGETED", "targets": too_many}},
    )
    assert r_oversize.status_code == 400
    assert r_oversize.json()["error"]["code"] == "INVALID_ARGUMENT"

    # 4) 幂等复放：同 key 重复提交不重复写库/审计
    n0 = asyncio.run(_count_notifications())
    a0 = asyncio.run(_count_send_audits())

    r1 = client.post(
        "/api/v1/admin/notifications/send",
        headers={"Authorization": f"Bearer {token_bound}", "Idempotency-Key": "k-idem"},
        json=body_target_self,
    )
    assert r1.status_code == 200
    assert r1.json()["success"] is True
    assert r1.json()["data"]["createdCount"] == 1

    r2 = client.post(
        "/api/v1/admin/notifications/send",
        headers={"Authorization": f"Bearer {token_bound}", "Idempotency-Key": "k-idem"},
        json=body_target_self,
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["createdCount"] == 1
    assert asyncio.run(_count_notifications()) == n0 + 1
    assert asyncio.run(_count_send_audits()) == a0 + 1

    # 5) 限流：每 Admin 20 次 / 10min，超出 429 RATE_LIMITED
    # 使用另一个 ADMIN，避免前面“幂等验证”的一次成功发送占用配额
    admin_bound2 = str(uuid4())
    asyncio.run(_seed_admin(admin_id=admin_bound2, phone="13800138001"))
    token_bound2, _ = create_admin_token(admin_id=admin_bound2)
    body_target_self2 = {
        "title": "t",
        "content": "c",
        "category": "SYSTEM",
        "audience": {"mode": "TARGETED", "targets": [{"receiverType": "ADMIN", "receiverId": admin_bound2}]},
    }

    for i in range(20):
        r_ok = client.post(
            "/api/v1/admin/notifications/send",
            headers={"Authorization": f"Bearer {token_bound2}", "Idempotency-Key": f"k-rate-{i}"},
            json=body_target_self2,
        )
        assert r_ok.status_code == 200

    r_rl = client.post(
        "/api/v1/admin/notifications/send",
        headers={"Authorization": f"Bearer {token_bound2}", "Idempotency-Key": "k-rate-over"},
        json=body_target_self2,
    )
    assert r_rl.status_code == 429
    assert r_rl.json()["error"]["code"] == "RATE_LIMITED"


