"""RequestId 中间件。

- 读取请求头中的 RequestId（默认 X-Request-Id）
- 若不存在则生成
- 写入 request.state.request_id 供统一响应与日志使用
"""

from __future__ import annotations

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.settings import settings


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        header_name = settings.request_id_header
        rid = request.headers.get(header_name) or str(uuid.uuid4())
        request.state.request_id = rid

        response = await call_next(request)
        response.headers[header_name] = rid
        return response
