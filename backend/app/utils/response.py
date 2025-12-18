"""统一响应体。

任务要求：统一响应体格式（success/data/error/requestId）。
"""

from __future__ import annotations

from typing import Any, Optional


def ok(*, data: Any = None, request_id: str) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "error": None,
        "requestId": request_id,
    }


def fail(*, code: str, message: str, request_id: str, details: Optional[Any] = None) -> dict[str, Any]:
    return {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "requestId": request_id,
    }
