"""健康检查接口（基础设施检查点使用）。

约定（平台级 vNext）：
- /health/live：仅说明进程存活（不检查外部依赖）
- /health/ready：检查关键依赖（DB/Redis）可用性
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.utils.db import get_session_factory
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    return ok(data={"status": "ok"}, request_id=request.state.request_id)


@router.get("/health/live")
async def health_live(request: Request):
    return ok(data={"status": "ok", "live": True}, request_id=request.state.request_id)


@router.get("/health/ready")
async def health_ready(request: Request):
    # DB
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(text("SELECT 1"))

    # Redis
    redis = get_redis()
    await redis.ping()

    return ok(data={"status": "ok", "ready": True}, request_id=request.state.request_id)
