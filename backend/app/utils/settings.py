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

    # JWT（阶段3：统一身份认证服务）
    jwt_secret: str = "change_me_jwt_secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = 604800

    # 微信小程序 code 换取 openid/unionid（阶段3-16）
    wechat_appid: str = ""
    wechat_secret: str = ""
    wechat_code_exchange_service_url: str = ""

    # Admin 认证（阶段3-17）
    admin_init_username: str = ""
    admin_init_password: str = ""
    jwt_secret_admin: str = "change_me_jwt_secret_admin"
    jwt_algorithm_admin: str = "HS256"
    jwt_admin_access_expire_seconds: int = 7200  # 2小时

    # 权益二维码签名（阶段5-29）
    # 约束：与 DEALER_SIGN_SECRET 密钥隔离；仅存后端环境变量，不可下发前端。
    entitlement_qr_sign_secret: str = "change_me_entitlement_qr_sign_secret"

    # 经销商参数签名（阶段7-44）
    # 约束：仅存后端环境变量，不可下发前端。
    # 环境变量名：DEALER_SIGN_SECRET
    dealer_sign_secret: str = "change_me_dealer_sign_secret"

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
