"""Provider 鉴权上下文（阶段12）。

规格来源：
- specs/health-services-platform/design.md -> RBAC：服务提供方侧数据范围裁决（providerId/venueId）
- specs/health-services-platform/tasks.md -> 阶段12「Provider 认证（v1）」

说明（v1）：
- token payload 仅用于定位 actorId/actorType；providerId 通过 DB 查询得到（与 design.md 一致）。
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select

from app.models.provider_staff import ProviderStaff
from app.models.provider_user import ProviderUser
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token
from app.utils.db import get_session_factory
from app.utils.jwt_provider_token import decode_and_validate_provider_token, token_blacklist_key
from app.utils.redis_client import get_redis


@dataclass(frozen=True)
class ProviderContext:
    actorType: str  # PROVIDER|PROVIDER_STAFF
    actorId: str
    providerId: str


async def require_provider_context(*, authorization: str | None) -> ProviderContext:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_provider_token(token=token)
    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    actor_type = str(payload["actorType"])
    actor_id = str(payload["sub"])

    session_factory = get_session_factory()
    async with session_factory() as session:
        if actor_type == "PROVIDER":
            user = (await session.scalars(select(ProviderUser).where(ProviderUser.id == actor_id).limit(1))).first()
            if user is None or user.status != "ACTIVE":
                raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
            return ProviderContext(actorType="PROVIDER", actorId=user.id, providerId=user.provider_id)

        staff = (await session.scalars(select(ProviderStaff).where(ProviderStaff.id == actor_id).limit(1))).first()
        if staff is None or staff.status != "ACTIVE":
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
        return ProviderContext(actorType="PROVIDER_STAFF", actorId=staff.id, providerId=staff.provider_id)


async def try_get_provider_context(*, authorization: str | None) -> ProviderContext | None:
    if not authorization:
        return None
    try:
        return await require_provider_context(authorization=authorization)
    except HTTPException:
        return None
