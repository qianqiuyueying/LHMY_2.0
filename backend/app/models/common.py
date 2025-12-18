"""通用字段/工具（模型层）。"""

from __future__ import annotations

import uuid


def new_uuid() -> str:
    """生成 UUID 字符串。

    说明：v1 以字符串形式作为主键，便于跨端与日志排障。
    """

    return str(uuid.uuid4())
