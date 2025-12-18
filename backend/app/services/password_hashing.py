"""密码哈希（bcrypt，v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> admin 认证：密码策略 bcrypt（cost=12 默认）
"""

from __future__ import annotations

import bcrypt


def hash_password(*, password: str) -> str:
    # bcrypt 默认 cost 为 12（符合规格默认）
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(*, password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False

