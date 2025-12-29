"""集成测试：Admin 转赠记录列表（BE-ADMIN-005）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-005

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

import app.models  # noqa: F401
from app.main import app
from app.models.base import Base
from app.models.entitlement_transfer import EntitlementTransfer
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


def test_admin_entitlement_transfers_list_filters():
    asyncio.run(_reset_db_and_redis())

    admin_id = str(uuid4())
    token, _jti = create_admin_token(admin_id=admin_id)

    tid = str(uuid4())
    from_owner = str(uuid4())
    to_owner = str(uuid4())
    entitlement_id = str(uuid4())

    async def _seed() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                EntitlementTransfer(
                    id=tid,
                    entitlement_id=entitlement_id,
                    from_owner_id=from_owner,
                    to_owner_id=to_owner,
                    transferred_at=datetime.utcnow(),
                )
            )
            await session.commit()

    asyncio.run(_seed())

    client = TestClient(app)

    resp = client.get(
        f"/api/v1/admin/entitlement-transfers?fromOwnerId={from_owner}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == tid
    assert items[0]["entitlementId"] == entitlement_id
