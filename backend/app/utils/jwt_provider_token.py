"""Provider JWT（阶段12：服务提供方后台服务）。

规格来源：
- specs/health-services-platform/design.md -> RBAC：actorType=PROVIDER/PROVIDER_STAFF（阶段12落地）
- specs/health-services-platform/tasks.md -> 阶段12「Provider 认证（v1）」

说明（v1）：
- token secret 与 USER/Admin 隔离（settings.jwt_secret_provider）
- v1 不实现 logout blacklist（后续如需要可按 admin 模式扩展）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import HTTPException

from app.utils.settings import settings


def create_provider_token(*, actor_type: str, actor_id: str) -> tuple[str, str]:
    """创建 provider access token。

    Args:
        actor_type: "PROVIDER" | "PROVIDER_STAFF"
        actor_id: provider_users.id 或 provider_staff.id

    Returns:
        (token, jti)
    """

    if actor_type not in {"PROVIDER", "PROVIDER_STAFF"}:
        raise ValueError("actor_type must be PROVIDER or PROVIDER_STAFF")

    now = datetime.now(tz=UTC)
    jti = str(uuid4())
    payload = {
        "sub": actor_id,
        "actorType": actor_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_provider_access_expire_seconds)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_provider, algorithm=settings.jwt_algorithm_provider)
    return token, jti


def decode_and_validate_provider_token(*, token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_provider, algorithms=[settings.jwt_algorithm_provider])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 已过期"}) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 无效"}) from exc

    if (
        payload.get("actorType") not in {"PROVIDER", "PROVIDER_STAFF"}
        or not payload.get("sub")
        or not payload.get("jti")
    ):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 无效"})
    return payload


def token_blacklist_key(*, jti: str) -> str:
    return f"provider:token:blacklist:{jti}"
