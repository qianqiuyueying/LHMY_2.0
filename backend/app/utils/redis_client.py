"""Redis 连接（缓存与会话）。

任务要求：配置 Redis 7.0 连接（缓存与会话）。
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.utils.settings import settings


_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db)
    return _redis
