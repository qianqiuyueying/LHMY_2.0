"""OpenAPI 兼容入口（v1）。

规格来源：
- specs/功能实现/admin/tasks.md -> T-F01（统一 API 文档入口）

说明：
- FastAPI 默认 OpenAPI 为 `/openapi.json`
- 为兼容 “API 都在 /api/v1 前缀” 的直觉，额外提供 `/api/v1/openapi.json`
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["openapi"], include_in_schema=False)


@router.get("/openapi.json")
async def openapi_json_v1(request: Request):
    # 直接复用应用自身 openapi 生成结果
    return request.app.openapi()

