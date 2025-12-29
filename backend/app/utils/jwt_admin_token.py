"""Admin JWT（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> Admin Token 策略（独立 JWT_SECRET_ADMIN + payload）
- specs/health-services-platform/design.md -> logout blacklist 机制
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import HTTPException

from app.utils.settings import settings


def create_admin_token(*, admin_id: str) -> tuple[str, str]:
    """创建 admin access token。

    Returns:
        (token, jti)
    """

    now = datetime.now(tz=UTC)
    jti = str(uuid4())
    payload = {
        "sub": admin_id,
        "actorType": "ADMIN",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_admin_access_expire_seconds)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_admin, algorithm=settings.jwt_algorithm_admin)
    return token, jti


def decode_and_validate_admin_token(*, token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_admin, algorithms=[settings.jwt_algorithm_admin])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 已过期"}) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 无效"}) from exc

    if payload.get("actorType") != "ADMIN" or not payload.get("sub") or not payload.get("jti"):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 无效"})

    return payload


def token_blacklist_key(*, jti: str) -> str:
    return f"admin:token:blacklist:{jti}"
