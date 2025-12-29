"""FastAPI 应用入口。

任务要求：
- 创建 FastAPI 应用入口和配置加载
- 配置 CORS、请求日志、异常处理中间件
- 实现统一响应体格式（success/data/error/requestId）
- 配置 OpenAPI/Swagger 文档自动生成
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.router import router as v1_router
from app.middleware.audit_log import AuditLogMiddleware
from app.middleware.exceptions import register_exception_handlers
from app.middleware.rbac_context import RbacContextMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.utils.db import get_session_factory
from app.utils.logging import setup_logging
from app.utils.settings import settings

logger = logging.getLogger(__name__)

def _is_production() -> bool:
    return str(getattr(settings, "app_env", "") or "").strip().lower() == "production"


def _require_non_default(*, name: str, value: str, forbidden_values: set[str]) -> None:
    v = (value or "").strip()
    if not v or v in forbidden_values:
        raise RuntimeError(f"missing or insecure config: {name}")


def _validate_production_settings() -> None:
    """生产环境启动门禁（v1 最小）。

    目的：避免带着默认密钥/空配置直接上线。
    约束：只校验“基础设施级”安全配置，不引入业务字段校验。
    """

    if not _is_production():
        return

    # JWT secrets（必须非默认）
    _require_non_default(
        name="JWT_SECRET",
        value=settings.jwt_secret,
        forbidden_values={"change_me_jwt_secret"},
    )
    _require_non_default(
        name="JWT_SECRET_ADMIN",
        value=settings.jwt_secret_admin,
        forbidden_values={"change_me_jwt_secret_admin"},
    )
    _require_non_default(
        name="JWT_SECRET_PROVIDER",
        value=settings.jwt_secret_provider,
        forbidden_values={"change_me_jwt_secret_provider"},
    )
    _require_non_default(
        name="JWT_SECRET_DEALER",
        value=settings.jwt_secret_dealer,
        forbidden_values={"change_me_jwt_secret_dealer"},
    )

    # 签名密钥（必须非默认）
    _require_non_default(
        name="ENTITLEMENT_QR_SIGN_SECRET",
        value=settings.entitlement_qr_sign_secret,
        forbidden_values={"change_me_entitlement_qr_sign_secret"},
    )
    _require_non_default(
        name="DEALER_SIGN_SECRET",
        value=settings.dealer_sign_secret,
        forbidden_values={"change_me_dealer_sign_secret"},
    )

    # 小程序登录：生产环境必须配置（否则用户无法登录）
    _require_non_default(name="WECHAT_APPID", value=settings.wechat_appid, forbidden_values=set())
    _require_non_default(name="WECHAT_SECRET", value=settings.wechat_secret, forbidden_values=set())

    # 微信支付预支付：生产环境必须配置（否则“立即支付”不可用）
    _require_non_default(name="WECHAT_PAY_MCH_ID", value=settings.wechat_pay_mch_id, forbidden_values=set())
    _require_non_default(name="WECHAT_PAY_APPID", value=settings.wechat_pay_appid, forbidden_values=set())
    _require_non_default(
        name="WECHAT_PAY_MCH_CERT_SERIAL", value=settings.wechat_pay_mch_cert_serial, forbidden_values=set()
    )
    _require_non_default(
        name="WECHAT_PAY_MCH_PRIVATE_KEY_PEM_OR_PATH",
        value=settings.wechat_pay_mch_private_key_pem_or_path,
        forbidden_values=set(),
    )
    _require_non_default(name="WECHAT_PAY_NOTIFY_URL", value=settings.wechat_pay_notify_url, forbidden_values=set())


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 静态资源（v1：上传图片落盘后从 /static 直接访问）
    # - 目录：backend/app/static
    # - URL：/static/uploads/...
    from pathlib import Path  # noqa: WPS433

    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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

    # Metrics（Prometheus）
    # - endpoint: /metrics（不进入 OpenAPI）
    # - 注意：Prometheus 抓取通常发生在内网；生产环境可再加白名单/IP 访问控制
    Instrumentator().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

    @app.on_event("startup")
    async def _startup_validate_production_settings() -> None:
        try:
            _validate_production_settings()
        except Exception:
            logger.exception("production settings validation failed")
            raise

    @app.on_event("startup")
    async def _startup_seed_admin() -> None:
        """按规格：首次启动（v1 开发/测试）若不存在则创建初始管理员账号。

        说明：
        - 由环境变量 `ADMIN_INIT_USERNAME/ADMIN_INIT_PASSWORD` 控制；为空则不做任何操作
        - 启动阶段 DB 可能尚未就绪（本地开发），失败时仅记录日志，不阻断启动
        """

        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                # 复用 admin_auth 内的最小种子逻辑（避免引入额外 seed 表/脚本）
                from app.api.v1.admin_auth import _ensure_admin_seed  # noqa: WPS433

                await _ensure_admin_seed(session)
        except Exception:  # noqa: BLE001
            logger.exception("admin seed failed (ignored)")

    return app


app = create_app()
