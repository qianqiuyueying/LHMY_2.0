"""异常处理。

任务要求：异常处理中间件。

这里以 FastAPI 官方推荐的“全局异常处理器”实现，保证所有错误统一包装为任务规定的响应体。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.response import fail


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # 约定：
        # - 若业务代码使用 HTTPException(detail={"code","message","details?"}) 抛错，则透传为统一错误码表中的 error.code。
        # - 否则保留兜底的 HTTP_EXCEPTION（兼容 FastAPI/Starlette 默认抛错）。
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=fail(
                    code=str(exc.detail.get("code")),
                    message=str(exc.detail.get("message")),
                    details=exc.detail.get("details"),
                    request_id=_request_id(request),
                ),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(
                code="HTTP_EXCEPTION",
                message=exc.detail if isinstance(exc.detail, str) else "请求错误",
                details=exc.detail if not isinstance(exc.detail, str) else None,
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content=fail(
                code="INVALID_ARGUMENT",
                message="参数不合法",
                details=exc.errors(),
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # 注意：生产环境不返回堆栈，避免泄露。
        return JSONResponse(
            status_code=500,
            content=fail(
                code="INTERNAL_ERROR",
                message="服务器内部错误",
                details=None,
                request_id=_request_id(request),
            ),
        )
