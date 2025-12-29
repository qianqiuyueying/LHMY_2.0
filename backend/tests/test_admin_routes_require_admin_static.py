"""静态门禁测试：/api/v1/admin/** 必须 require_admin（一刀切）。

规格依据（单一真相来源）：
- specs-prod/admin/requirements.md#AUTH-002
- specs-prod/admin/tasks.md#TASK-P0-001

说明：
- 这是“结构性防回归”测试，不发真实 HTTP 请求，不依赖请求体/参数校验顺序。
- 仅豁免必须未登录也能调用的 admin auth 端点（login/2fa）。
"""

from __future__ import annotations

from fastapi.routing import APIRoute


def _has_require_admin(route: APIRoute) -> bool:
    from app.api.v1.deps import require_admin

    target = require_admin
    seen: set[int] = set()
    stack = list(getattr(route.dependant, "dependencies", []) or [])
    while stack:
        dep = stack.pop()
        if id(dep) in seen:
            continue
        seen.add(id(dep))
        if getattr(dep, "call", None) is target:
            return True
        stack.extend(getattr(dep, "dependencies", []) or [])
    return False


def test_all_admin_routes_require_admin() -> None:
    # pytest 的 backend/tests/conftest.py 会把 backend 加到 sys.path，确保能 import app.*
    from app.main import app

    allowlist = {
        ("/api/v1/admin/auth/login", frozenset({"POST"})),
        ("/api/v1/admin/auth/2fa/challenge", frozenset({"POST"})),
        ("/api/v1/admin/auth/2fa/verify", frozenset({"POST"})),
    }

    missing: list[str] = []
    for r in app.router.routes:
        if not isinstance(r, APIRoute):
            continue
        if not r.path.startswith("/api/v1/admin/"):
            continue
        methods = frozenset(r.methods or [])
        if (r.path, methods) in allowlist:
            continue
        if not _has_require_admin(r):
            missing.append(f"{r.path} {','.join(sorted(methods))} {getattr(r.endpoint, '__name__', '<lambda>')}")

    assert missing == [], "Missing require_admin on admin routes:\\n" + "\\n".join(sorted(missing))


