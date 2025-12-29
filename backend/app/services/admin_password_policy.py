"""管理员密码策略（TASK-P0-005）。

规格来源（单一真相来源）：
- specs-prod/admin/security.md#1.4.2 密码策略（Password Policy）
"""

from __future__ import annotations

import re


_BLACKLIST = {
    "1234567890",
    "12345678",
    "password",
    "admin123",
    "qwertyuiop",
}


def validate_admin_password(*, username: str, new_password: str) -> str | None:
    """校验管理员新密码是否满足策略。

    Returns:
        None if ok, otherwise error message.
    """

    u = str(username or "").strip().lower()
    p = str(new_password or "")

    if len(p) < 10:
        return "新密码长度至少为 10 位"

    if u and p.strip().lower() == u:
        return "新密码不能与用户名相同"

    if p.strip().lower() in _BLACKLIST:
        return "新密码过于简单，请更换"

    has_upper = bool(re.search(r"[A-Z]", p))
    has_lower = bool(re.search(r"[a-z]", p))
    has_digit = bool(re.search(r"\d", p))
    has_special = bool(re.search(r"[^A-Za-z0-9]", p))
    categories = sum([has_upper, has_lower, has_digit, has_special])

    if categories < 2:
        return "新密码复杂度不足：需满足「大写/小写/数字/特殊字符」至少 2 类"

    return None


