"""数据库连接（MySQL 8.0，SQLAlchemy async）。

任务要求：配置 MySQL 8.0 连接池（SQLAlchemy async）。
"""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.utils.settings import settings


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _in_pytest() -> bool:
    # pytest 会注入 PYTEST_CURRENT_TEST；同时我们也允许通过 RUN_INTEGRATION_TESTS 显式开启“测试模式”
    return os.getenv("PYTEST_CURRENT_TEST") is not None or os.getenv("RUN_INTEGRATION_TESTS") == "1"


def get_engine() -> AsyncEngine:
    global _engine
    # 注意：在 Windows + pytest + asyncio.run 的组合下，如果复用全局 engine/连接池，
    # 容易在 event loop 切换后触发 “Event loop is closed / NoneType has no attribute send”。
    # 因此测试模式下不复用全局 engine，并关闭连接池复用（NullPool）。
    if _in_pytest():
        return create_async_engine(
            settings.mysql_dsn(),
            poolclass=NullPool,
            pool_pre_ping=False,
        )

    if _engine is None:
        _engine = create_async_engine(settings.mysql_dsn(), pool_pre_ping=True, pool_recycle=3600)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _in_pytest():
        return async_sessionmaker(bind=get_engine(), expire_on_commit=False)

    if _session_factory is None:
        _session_factory = async_sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory
