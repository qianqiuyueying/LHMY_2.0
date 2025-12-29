"""Celery 应用入口（v2：异步任务/定时任务）。

规格来源：
- specs/health-services-platform/tasks.md -> REQ-ECOMMERCE-P0-001（库存超时释放等后台任务）

约束：
- broker 复用 docker-compose.yml 的 RabbitMQ
- result backend 复用 Redis（也可用于分布式锁/去重）
"""

from __future__ import annotations

from celery import Celery

from app.utils.settings import settings


def _broker_url() -> str:
    # 优先从环境变量显式配置；否则按 compose 默认的 rabbitmq 服务名拼接
    raw = str(getattr(settings, "celery_broker_url", "") or "").strip()
    if raw:
        return raw
    user = str(getattr(settings, "rabbitmq_default_user", "") or "guest")
    pwd = str(getattr(settings, "rabbitmq_default_pass", "") or "guest")
    host = str(getattr(settings, "rabbitmq_host", "") or "rabbitmq")
    port = int(getattr(settings, "rabbitmq_port", 0) or 5672)
    vhost = str(getattr(settings, "rabbitmq_vhost", "") or "/")
    # vhost 在 url 里需要转义，最小实现先只支持默认 /
    if vhost not in ("", "/"):
        vhost = "/"
    return f"amqp://{user}:{pwd}@{host}:{port}{vhost}"


def _backend_url() -> str:
    raw = str(getattr(settings, "celery_result_backend", "") or "").strip()
    if raw:
        return raw
    host = str(getattr(settings, "redis_host", "") or "redis")
    port = int(getattr(settings, "redis_port", 0) or 6379)
    db = int(getattr(settings, "redis_db", 0) or 0)
    return f"redis://{host}:{port}/{db}"


celery_app = Celery(
    "lhmy",
    broker=_broker_url(),
    backend=_backend_url(),
    include=["app.tasks.inventory"],
)

# v1 最小：使用 UTC，避免跨时区漂移；未来如需本地时区可通过配置扩展
celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
)


