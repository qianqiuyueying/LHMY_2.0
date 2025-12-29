"""Redis 连接（缓存与会话）。

任务要求：配置 Redis 7.0 连接（缓存与会话）。
"""

from __future__ import annotations

import os

from redis.asyncio import Redis

from app.utils.settings import settings


_redis: Redis | None = None


def _in_pytest() -> bool:
    return os.getenv("PYTEST_CURRENT_TEST") is not None or os.getenv("RUN_INTEGRATION_TESTS") == "1"


def get_redis() -> Redis:
    global _redis
    # 同 db.py：测试模式下避免复用跨 event loop 的全局连接对象（Windows 上容易炸）
    if _in_pytest():
        return Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db)

    if _redis is None:
        _redis = Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db)
    return _redis
