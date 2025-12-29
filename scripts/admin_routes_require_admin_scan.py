"""扫描：所有 /api/v1/admin/** 路由是否强制 require_admin。

规格依据（单一真相来源）：
- specs-prod/admin/requirements.md#AUTH-002（/api/v1/admin/** 仅 ADMIN）
- specs-prod/admin/tasks.md#TASK-P0-001（后端每条 admin API 明确依赖 require_admin）

用法（PowerShell）：
  $env:PYTHONPATH="backend"
  uv run python scripts/admin_routes_require_admin_scan.py
"""

from __future__ import annotations

from fastapi.routing import APIRoute


def _has_require_admin(route: APIRoute) -> bool:
    # 延迟导入：确保 PYTHONPATH=backend 时能导入 app.*
    from app.api.v1.deps import require_admin

    target = require_admin
    seen: set[int] = set()
    stack = list(getattr(route.dependant, "dependencies", []) or [])
    while stack:
        dep = stack.pop()
        if id(dep) in seen:
            continue
        seen.add(id(dep))
        call = getattr(dep, "call", None)
        if call is target:
            return True
        stack.extend(getattr(dep, "dependencies", []) or [])
    return False


def main() -> int:
    from app.main import app

    # 豁免：必须未登录也能调用的 admin auth 端点（生产口径）
    allowlist = {
        ("/api/v1/admin/auth/login", frozenset({"POST"})),
        ("/api/v1/admin/auth/2fa/challenge", frozenset({"POST"})),
        ("/api/v1/admin/auth/2fa/verify", frozenset({"POST"})),
    }

    missing: list[tuple[str, str, str]] = []
    for r in app.router.routes:
        if not isinstance(r, APIRoute):
            continue
        if not r.path.startswith("/api/v1/admin/"):
            continue
        methods = frozenset(r.methods or [])
        if (r.path, methods) in allowlist:
            continue
        if not _has_require_admin(r):
            missing.append((r.path, ",".join(sorted(methods)), getattr(r.endpoint, "__name__", "<lambda>")))

    print("missing_require_admin_count=", len(missing))
    for p, ms, name in sorted(missing):
        print(p, ms, name)
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())


