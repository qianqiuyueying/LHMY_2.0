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
        logger.info(
            "request_id=%s method=%s path=%s status=%s cost_ms=%.2f",
            rid,
            request.method,
            request.url.path,
            response.status_code,
            cost_ms,
        )
        return response
