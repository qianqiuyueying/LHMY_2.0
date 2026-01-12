"""异常处理。

任务要求：异常处理中间件。

这里以 FastAPI 官方推荐的“全局异常处理器”实现，保证所有错误统一包装为任务规定的响应体。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.response import fail


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _code_from_status(status_code: int) -> str:
    # v1 最小：把“框架级 HTTP 错误”映射到稳定错误码，避免前端只能看到 HTTP_EXCEPTION
    if status_code == 400:
        return "INVALID_ARGUMENT"
    if status_code == 401:
        # 统一口径：401 一律使用 UNAUTHENTICATED（与 specs-prod/admin/api-contracts.md#7 一致）
        return "UNAUTHENTICATED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 405:
        return "METHOD_NOT_ALLOWED"
    if status_code == 409:
        return "STATE_CONFLICT"
    if status_code == 429:
        return "RATE_LIMITED"
    if 500 <= status_code:
        return "INTERNAL_ERROR"
    return "HTTP_EXCEPTION"


def _json_safe(value: Any) -> Any:
    """把可能包含不可 JSON 序列化对象（如 ValueError）的结构转为 JSON-safe。

    背景：Pydantic v2 的 `RequestValidationError.errors()` 里，可能在 `ctx` 放入异常对象，
    若直接作为 JSONResponse.content 会导致序列化失败（进而变成 500，掩盖真实 400 原因）。
    """

    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            out[str(k)] = _json_safe(v)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    # 兜底：避免任何未知对象破坏响应序列化
    return str(value)


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
                    details=_json_safe(exc.detail.get("details")),
                    request_id=_request_id(request),
                ),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(
                code=_code_from_status(int(exc.status_code)),
                message=exc.detail if isinstance(exc.detail, str) else "请求错误",
                details=_json_safe(exc.detail) if not isinstance(exc.detail, str) else None,
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
                details=_json_safe(exc.errors()),
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

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        # 统一处理数据库唯一约束/外键约束等冲突
        return JSONResponse(
            status_code=409,
            content=fail(
                code="STATE_CONFLICT",
                message="资源冲突",
                details={"db": str(exc.__class__.__name__)},
                request_id=_request_id(request),
            ),
        )
