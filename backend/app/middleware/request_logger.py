"""请求日志中间件。

任务要求：请求日志中间件。
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("lhmy.request")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        cost_ms = (time.perf_counter() - start) * 1000

        rid = getattr(request.state, "request_id", "")
        actor = getattr(request.state, "actor", None)
        actor_type = getattr(actor, "actor_type", None)
        actor_id = getattr(actor, "sub", None)
        ip = getattr(getattr(request, "client", None), "host", None)
        ua = request.headers.get("User-Agent")
        logger.info(
            "request_id=%s method=%s path=%s status=%s cost_ms=%.2f actor_type=%s actor_id=%s ip=%s ua=%s",
            rid,
            request.method,
            request.url.path,
            response.status_code,
            cost_ms,
            actor_type,
            actor_id,
            ip,
            ua,
        )
        return response
