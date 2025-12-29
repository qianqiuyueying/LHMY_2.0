"""配置加载。

说明：遵循任务清单“配置环境变量模板文件（.env.example）”。
这里通过 Pydantic Settings 统一读取环境变量，并支持从 .env 文件加载。
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。

    约束：只放基础设施阶段必要配置，避免提前引入业务字段。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 基础信息
    app_name: str = "LHMY_Health_Service_Platform"
    app_env: str = "development"

    # CORS
    cors_origins: str = ""

    # Assets / uploads
    # - ASSETS_PUBLIC_BASE_URL: 对外访问静态资源的基址（例如 https://cdn.example.com）
    #   - 为空时：返回相对路径（如 /static/uploads/...），由同域 Nginx/反代提供
    # - ASSETS_STORAGE: 预留存储类型（LOCAL/OSS），本期默认 LOCAL
    assets_public_base_url: str = ""
    assets_storage: str = "LOCAL"

    # RequestId
    request_id_header: str = "X-Request-Id"

    # MySQL
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_user: str = "lhmy"
    mysql_password: str = ""
    mysql_database: str = "lhmy"

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # RabbitMQ（docker-compose.yml 默认提供；Celery broker 复用）
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_default_user: str = "guest"
    rabbitmq_default_pass: str = "guest"
    rabbitmq_vhost: str = "/"

    # Celery（异步任务队列/定时任务）
    # - 默认 broker: RabbitMQ（由上面 rabbitmq_* 组合）
    # - 默认 result backend: Redis（由上面 redis_* 组合）
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # JWT（阶段3：统一身份认证服务）
    jwt_secret: str = "change_me_jwt_secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = 604800

    # 微信小程序 code 换取 openid/unionid（阶段3-16）
    wechat_appid: str = ""
    wechat_secret: str = ""
    wechat_code_exchange_service_url: str = ""

    # 微信支付（REQ-P0-001：回调验签/解密）
    # 说明：
    # - v1 仅用于回调（notify）侧验签与资源解密；“下单/签名/预支付”等契约需在规格补全后再实现。
    # - 平台证书建议以文件方式挂载；也支持直接填 PEM 文本。
    wechat_pay_api_v3_key: str = ""  # 32字节（ASCII）APIv3Key
    wechat_pay_platform_cert_serial: str = ""  # 平台证书序列号（用于校验 wechatpay-serial）
    wechat_pay_platform_cert_pem_or_path: str = ""  # PEM 文本或证书文件路径

    # 微信支付 JSAPI 预支付（小程序端，v1）
    # 说明：
    # - 用于 /api/v1/orders/{id}/pay 生成可用于 wx.requestPayment 的 wechatPayParams
    # - 若生产环境缺失，将被启动门禁阻止（见 app/main.py）
    wechat_pay_mch_id: str = ""  # 商户号 mchid
    wechat_pay_appid: str = ""  # 小程序 appid（通常与 wechat_appid 相同）
    wechat_pay_mch_cert_serial: str = ""  # 商户证书序列号（请求头 Wechatpay-Serial）
    wechat_pay_mch_private_key_pem_or_path: str = ""  # 商户私钥 PEM 文本或文件路径
    wechat_pay_notify_url: str = ""  # 支付回调地址（公网 https）
    wechat_pay_gateway_base_url: str = "https://api.mch.weixin.qq.com"

    # Admin 认证（阶段3-17）
    admin_init_username: str = ""
    admin_init_password: str = ""
    jwt_secret_admin: str = "change_me_jwt_secret_admin"
    jwt_algorithm_admin: str = "HS256"
    jwt_admin_access_expire_seconds: int = 7200  # 2小时

    # Provider 认证（阶段12）
    # 说明：与 USER/Admin token 隔离，避免跨端/跨后台串用。
    jwt_secret_provider: str = "change_me_jwt_secret_provider"
    jwt_algorithm_provider: str = "HS256"
    jwt_provider_access_expire_seconds: int = 7200  # 2小时

    # Provider 初始账号（用于开发/测试环境最小可执行）
    # 说明：
    # - 目标：提供“可重复获取账号”的路径，避免因无注册入口导致无法登录验证 Provider 端。
    # - 与 Admin 的 ADMIN_INIT_* 口径一致：仅当环境变量有值时才会自动创建（若不存在同名账号）。
    provider_init_username: str = ""
    provider_init_password: str = ""
    provider_init_provider_name: str = ""  # 可选：Provider 主体名称（默认等同 username）

    provider_staff_init_username: str = ""
    provider_staff_init_password: str = ""

    # Dealer JWT（阶段：经销商后台）
    # 说明：与 USER/Admin/Provider token 隔离，避免跨端串用。
    jwt_secret_dealer: str = "change_me_jwt_secret_dealer"
    jwt_algorithm_dealer: str = "HS256"
    jwt_dealer_access_expire_seconds: int = 7200  # 2小时

    # Dealer 初始账号（用于开发/测试环境最小可执行）
    # 说明：避免因无注册入口导致无法登录验证 Dealer 端（仅当以下变量有值时才会自动创建）。
    dealer_init_username: str = ""
    dealer_init_password: str = ""
    dealer_init_dealer_name: str = ""  # 可选：Dealer 主体名称（默认等同 username）

    # 权益二维码签名（阶段5-29）
    # 约束：与 DEALER_SIGN_SECRET 密钥隔离；仅存后端环境变量，不可下发前端。
    entitlement_qr_sign_secret: str = "change_me_entitlement_qr_sign_secret"

    # 经销商参数签名（阶段7-44）
    # 约束：仅存后端环境变量，不可下发前端。
    # 环境变量名：DEALER_SIGN_SECRET
    dealer_sign_secret: str = "change_me_dealer_sign_secret"

    # 电商：支付超时（用于库存占用超时释放，v2）
    # - 默认 15 分钟
    order_payment_timeout_seconds: int = 900

    def mysql_dsn(self) -> str:
        # SQLAlchemy async + aiomysql
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins.strip():
            return []
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
