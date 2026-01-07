"""UTC 时间工具。

目的：
- 避免使用已弃用的 datetime.utcnow()（Python 未来版本将移除）
- 统一项目内“DB 存储为 UTC 的无时区 DATETIME（naive）”口径
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """返回 naive UTC datetime（tzinfo=None）。"""

    return datetime.now(tz=UTC).replace(tzinfo=None)


