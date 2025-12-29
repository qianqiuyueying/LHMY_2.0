"""集成测试：Admin 通知接口（BE-ADMIN-002）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-002

说明：
- 需要 MySQL/Redis，因此仅在 RUN_INTEGRATION_TESTS=1 时运行。
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.enums import NotificationReceiverType, NotificationStatus
from app.models.notification import Notification
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


def test_admin_notifications_list_and_read():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    other_admin_id = str(uuid4())

    n1_id = str(uuid4())
    n2_id = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Notification(
                    id=n1_id,
                    receiver_type=NotificationReceiverType.ADMIN.value,
                    receiver_id=admin_id,
                    title="t1",
                    content="c1",
                    status=NotificationStatus.UNREAD.value,
                    created_at=datetime.utcnow(),
                    read_at=None,
                )
            )
            session.add(
                Notification(
                    id=n2_id,
                    receiver_type=NotificationReceiverType.ADMIN.value,
                    receiver_id=other_admin_id,
                    title="t2",
                    content="c2",
                    status=NotificationStatus.UNREAD.value,
                    created_at=datetime.utcnow(),
                    read_at=None,
                )
            )
            await session.commit()

    asyncio.run(_seed())

    token, _jti = create_admin_token(admin_id=admin_id)
    client = TestClient(app)

    # 1) list：只返回自己的
    r1 = client.get("/api/v1/admin/notifications", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200
    items = r1.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == n1_id
    assert items[0]["status"] == "UNREAD"

    # 2) mark read
    r2 = client.post(f"/api/v1/admin/notifications/{n1_id}/read", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "READ"
    assert r2.json()["data"]["readAt"]

    # 3) list unread -> empty
    r3 = client.get(
        "/api/v1/admin/notifications?status=UNREAD",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 200
    assert r3.json()["data"]["total"] == 0

    # 4) DB 断言：状态已更新
    async def _assert_db() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            n = (await session.scalars(select(Notification).where(Notification.id == n1_id).limit(1))).first()
            assert n is not None
            assert n.status == NotificationStatus.READ.value
            assert n.read_at is not None

    asyncio.run(_assert_db())
