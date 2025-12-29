"""统一权限校验依赖（REQ-P1-003）。

规格来源：
- specs/health-services-platform/后端升级需求与变更清单（v1）.md -> REQ-P1-003

说明：
- 依赖优先复用 RbacContextMiddleware 注入的 request.state.actor（避免重复解码）
- 若 middleware 未注入或本端点要求强认证，则使用 Authorization 解析并校验黑名单
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from sqlalchemy import select

from app.models.admin import Admin
from app.utils.db import get_session_factory
from app.services.provider_auth_context import ProviderContext, require_provider_context
from app.services.rbac import ActorContext, ActorType, parse_actor_from_bearer_token, require_actor_types
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token
from app.utils.redis_client import get_redis


async def optional_actor(request: Request, authorization: str | None = Header(default=None)) -> ActorContext | None:
    actor = getattr(request.state, "actor", None)
    if isinstance(actor, ActorContext):
        return actor
    if not authorization:
        return None
    try:
        token = _extract_bearer_token(authorization)
        return await parse_actor_from_bearer_token(token=token, redis=get_redis())
    except HTTPException:
        return None


async def optional_user(request: Request, authorization: str | None = Header(default=None)) -> ActorContext | None:
    """可选 USER（REQ-P1-003 示例中的 optional_user）。"""

    actor = await optional_actor(request, authorization)
    if actor is None:
        return None
    return actor if actor.actor_type == ActorType.USER else None


async def require_user(request: Request, authorization: str | None = Header(default=None)) -> ActorContext:
    actor = await optional_actor(request, authorization)
    if actor is None:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    require_actor_types(actor=actor, allowed={ActorType.USER})
    return actor


async def require_admin(request: Request, authorization: str | None = Header(default=None)) -> ActorContext:
    actor = await optional_actor(request, authorization)
    if actor is None:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    require_actor_types(actor=actor, allowed={ActorType.ADMIN})
    return actor


async def require_admin_phone_bound(
    request: Request, authorization: str | None = Header(default=None)
) -> ActorContext:
    """高风险操作门禁：要求 ADMIN 已绑定手机号（用于 2FA）。

    规格来源：specs-prod/admin/security.md#1.4.4（未绑定允许登录，但高风险操作前置要求先绑定）
    """

    actor = await require_admin(request, authorization)
    session_factory = get_session_factory()
    async with session_factory() as session:
        admin = (await session.scalars(select(Admin).where(Admin.id == str(actor.sub)).limit(1))).first()
    if admin is None or admin.status != "ACTIVE":
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    if not (admin.phone or "").strip():
        raise HTTPException(status_code=403, detail={"code": "ADMIN_PHONE_REQUIRED", "message": "请先绑定手机号开启2FA"})
    return actor


async def require_provider(authorization: str | None = Header(default=None)) -> ProviderContext:
    return await require_provider_context(authorization=authorization)

