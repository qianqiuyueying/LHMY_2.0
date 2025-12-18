"""健康检查接口（基础设施检查点使用）。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.utils.response import ok

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    return ok(data={"status": "ok"}, request_id=request.state.request_id)
