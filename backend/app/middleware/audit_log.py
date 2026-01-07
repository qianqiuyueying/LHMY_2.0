"""审计日志自动记录中间件（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 审计日志（AuditLog，v1 最小可执行）
- specs/health-services-platform/design.md -> E-5 全局审计日志查询（写侧由中间件自动记录）
- specs/health-services-platform/tasks.md -> 阶段10-59.1/59.3

v1 约束：
- 仅记录关键操作元数据（禁止存敏感明文：密码/短信验证码/Authorization/token/对话正文等）
- 默认仅对“写操作”留痕（POST/PUT/PATCH/DELETE + 少数路径动作），GET 不记录
"""

from __future__ import annotations

import logging
from typing import Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.datetime_utc import utcnow

logger = logging.getLogger("lhmy.audit")


def _infer_action(*, method: str, path: str) -> AuditAction | None:
    p = path.lower()

    # auth 特例（避免误归类为 CREATE/UPDATE）
    if p.endswith("/admin/auth/logout"):
        return AuditAction.LOGOUT

    # path action 优先（更精确）
    if p.endswith("/publish"):
        return AuditAction.PUBLISH
    if p.endswith("/offline"):
        return AuditAction.OFFLINE
    if p.endswith("/approve"):
        return AuditAction.APPROVE
    if p.endswith("/reject"):
        return AuditAction.REJECT

    m = method.upper()
    if m == "POST":
        return AuditAction.CREATE
    if m in {"PUT", "PATCH"}:
        return AuditAction.UPDATE
    # v1：DELETE 很少用，但仍记录为 UPDATE（不引入新 action）
    if m == "DELETE":
        return AuditAction.UPDATE
    return None


def _infer_resource(*, path: str) -> tuple[str, str | None]:
    # path 形如：/api/v1/admin/products/{id}/approve
    rest = path
    if rest.startswith("/api/v1/"):
        rest = rest[len("/api/v1/") :]
    rest = rest.strip("/")
    parts = [p for p in rest.split("/") if p]

    # AI 对话：由业务端点写入更丰富的元数据审计（resourceType=AI_CHAT）
    if len(parts) >= 2 and parts[0] == "ai" and parts[1] == "chat":
        return ("AI_CHAT", None)

    if len(parts) >= 2 and parts[0] == "admin" and parts[1] == "enterprise-bindings":
        return ("ENTERPRISE_BINDING", parts[2] if len(parts) >= 3 else None)
    if len(parts) >= 2 and parts[0] == "admin" and parts[1] == "products":
        return ("PRODUCT", parts[2] if len(parts) >= 3 else None)
    if len(parts) >= 2 and parts[0] == "admin" and parts[1] == "orders":
        return ("ORDER", parts[2] if len(parts) >= 3 else None)
    if len(parts) >= 2 and parts[0] == "admin" and parts[1] == "after-sales":
        return ("AFTER_SALE", parts[2] if len(parts) >= 3 else None)
    if len(parts) >= 1 and parts[0] == "orders":
        return ("ORDER", parts[1] if len(parts) >= 2 else None)

    # 兜底：以首段作为资源类型（大写）
    return (parts[0].upper() if parts else "UNKNOWN", parts[1] if len(parts) >= 2 else None)


def _query_keys(request: Request) -> list[str]:
    # 仅记录 key，不记录 value（避免泄露敏感信息）
    try:
        return sorted({str(k) for k in request.query_params.keys()})
    except Exception:  # noqa: BLE001
        return []


def _should_audit(*, request: Request, action: AuditAction | None) -> bool:
    if action is None:
        return False
    # v1：不记录健康检查
    if request.url.path.startswith("/api/v1/health"):
        return False
    # v1：AI 对话由业务端点写入 richer 审计记录（避免重复记录）
    if request.url.path.startswith("/api/v1/ai/chat"):
        return False
    # v1：不记录 read-only
    if request.method.upper() == "GET":
        return False
    return True


def _truncate(s: str | None, limit: int) -> str | None:
    if not s:
        return None
    raw = str(s)
    return raw if len(raw) <= limit else raw[:limit]


def _safe_metadata(metadata: dict) -> dict:
    """确保 metadata 不包含敏感字段（v1：白名单化）。"""

    allowed_keys = {"method", "path", "statusCode", "queryKeys", "requestId"}
    return {k: metadata.get(k) for k in allowed_keys if k in metadata}


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        try:
            actor: ActorContext | None = getattr(request.state, "actor", None)
            if actor is None:
                return response

            action = _infer_action(method=request.method, path=request.url.path)
            if action is None:
                return response
            if not _should_audit(request=request, action=action):
                return response

            resource_type, resource_id = _infer_resource(path=request.url.path)
            rid = getattr(request.state, "request_id", "")

            meta = _safe_metadata(
                {
                    "method": request.method.upper(),
                    "path": request.url.path,
                    "statusCode": int(response.status_code),
                    "queryKeys": _query_keys(request),
                    "requestId": str(rid) if rid else None,
                }
            )

            log = AuditLog(
                id=str(uuid4()),
                actor_type=actor.actor_type.value,
                actor_id=str(actor.sub),
                action=action.value,
                resource_type=str(resource_type),
                resource_id=str(resource_id) if resource_id else None,
                summary=_truncate(
                    f"{action.value} {resource_type}{(' ' + str(resource_id)) if resource_id else ''}", 512
                ),
                ip=_truncate(getattr(getattr(request, "client", None), "host", None), 64),
                user_agent=_truncate(request.headers.get("User-Agent"), 512),
                metadata_json=meta,
                created_at=utcnow(),
            )

            session_factory = get_session_factory()
            async with session_factory() as session:
                session.add(log)
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            # 审计失败不得影响主流程
            logger.warning("audit_log_failed path=%s err=%s", request.url.path, repr(exc))

        return response
