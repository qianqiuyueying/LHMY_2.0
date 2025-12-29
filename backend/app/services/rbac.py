"""RBAC（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 1A. 权限与数据范围（RBAC）

v1 边界（按规格）：
- 阶段3只落地 USER/ADMIN 的认证与基础上下文
- v1 不做“动作级别”细分，仅做“数据范围过滤 + 403”
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fastapi import HTTPException
from redis.asyncio import Redis

from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_dealer_token import decode_and_validate_dealer_token
from app.utils.jwt_provider_token import decode_and_validate_provider_token, token_blacklist_key as provider_token_blacklist_key
from app.utils.jwt_token import decode_and_validate_user_token, token_blacklist_key as user_token_blacklist_key


class ActorType(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"
    DEALER = "DEALER"
    PROVIDER = "PROVIDER"
    PROVIDER_STAFF = "PROVIDER_STAFF"


@dataclass(frozen=True)
class ActorContext:
    actor_type: ActorType
    sub: str
    channel: str | None = None


async def parse_actor_from_bearer_token(*, token: str, redis: Redis) -> ActorContext:
    """根据 token 解析操作者上下文。

    约束：
    - admin token 与 user token secret 分离，因此可先尝试 admin 解码。
    - v1 仅落地 USER/ADMIN。
    """

    # 1) 尝试 admin
    try:
        payload = decode_and_validate_admin_token(token=token)
        jti = str(payload["jti"])
        if await redis.exists(token_blacklist_key(jti=jti)):
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
        return ActorContext(actor_type=ActorType.ADMIN, sub=str(payload["sub"]), channel=None)
    except HTTPException:
        # 继续尝试 user
        pass

    # 2) 尝试 provider
    try:
        payload = decode_and_validate_provider_token(token=token)
        jti = str(payload["jti"])
        if await redis.exists(provider_token_blacklist_key(jti=jti)):
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
        actor_type = str(payload["actorType"])
        if actor_type == ActorType.PROVIDER.value:
            return ActorContext(actor_type=ActorType.PROVIDER, sub=str(payload["sub"]), channel=None)
        return ActorContext(actor_type=ActorType.PROVIDER_STAFF, sub=str(payload["sub"]), channel=None)
    except HTTPException:
        pass

    # 3) 尝试 dealer
    try:
        payload = decode_and_validate_dealer_token(token=token)
        return ActorContext(actor_type=ActorType.DEALER, sub=str(payload["sub"]), channel=None)
    except HTTPException:
        pass

    # 4) 尝试 user
    payload = decode_and_validate_user_token(token=token)
    jti = str(payload["jti"])
    if await redis.exists(user_token_blacklist_key(jti=jti)):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return ActorContext(
        actor_type=ActorType.USER,
        sub=str(payload["sub"]),
        channel=str(payload.get("channel")) if payload.get("channel") else None,
    )


def require_actor_types(*, actor: ActorContext, allowed: set[ActorType]) -> None:
    if actor.actor_type not in allowed:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限访问"})
