"""RBAC 上下文中间件（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> RBAC：中间件从 token 解析 actorType/sub，供数据范围裁决使用

说明：
- v1 仅在 request.state 注入 actorContext（不主动拦截请求）。
- 具体端点的权限/数据范围校验由依赖或业务逻辑负责。
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.rbac import ActorContext, parse_actor_from_bearer_token
from app.utils.redis_client import get_redis


class RbacContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.actor = None  # type: ignore[attr-defined]

        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                actor: ActorContext = await parse_actor_from_bearer_token(token=token, redis=get_redis())
                request.state.actor = actor  # type: ignore[attr-defined]
            except Exception:
                # 无效 token 不在此处拦截，由具体端点决定是否要求登录
                request.state.actor = None  # type: ignore[attr-defined]

        return await call_next(request)

