"""FastAPI 应用入口。

任务要求：
- 创建 FastAPI 应用入口和配置加载
- 配置 CORS、请求日志、异常处理中间件
- 实现统一响应体格式（success/data/error/requestId）
- 配置 OpenAPI/Swagger 文档自动生成
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.middleware.audit_log import AuditLogMiddleware
from app.middleware.exceptions import register_exception_handlers
from app.middleware.rbac_context import RbacContextMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.utils.logging import setup_logging
from app.utils.settings import settings


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 中间件
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RequestLoggerMiddleware)
    app.add_middleware(RbacContextMiddleware)
    app.add_middleware(AuditLogMiddleware)

    origins = settings.cors_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 异常处理
    register_exception_handlers(app)

    # 路由
    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()
