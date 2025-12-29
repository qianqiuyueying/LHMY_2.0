"""Dealer JWT（经销商后台服务）。

规格来源：
- specs/health-services-platform/design.md -> RBAC：DEALER（经销商后台）

说明（v1）：
- token secret 与 USER/Admin/Provider 隔离（settings.jwt_secret_dealer）
- v1 不实现 logout blacklist（如需要可按 admin 模式扩展）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import HTTPException

from app.utils.settings import settings


def create_dealer_token(*, actor_id: str) -> tuple[str, str]:
    """创建 dealer access token。

    Args:
        actor_id: dealer_users.id

    Returns:
        (token, jti)
    """

    now = datetime.now(tz=UTC)
    jti = str(uuid4())
    payload = {
        "sub": actor_id,
        "actorType": "DEALER",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_dealer_access_expire_seconds)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_dealer, algorithm=settings.jwt_algorithm_dealer)
    return token, jti


def decode_and_validate_dealer_token(*, token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_dealer, algorithms=[settings.jwt_algorithm_dealer])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 已过期"}) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 无效"}) from exc

    if payload.get("actorType") != "DEALER" or not payload.get("sub") or not payload.get("jti"):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 无效"})
    return payload

