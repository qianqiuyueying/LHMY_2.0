"""JWT Token 工具（阶段3：统一身份认证）。

规格来源：
- specs/health-services-platform/design.md -> API 通用约定：Bearer Token
- specs/health-services-platform/design.md -> 错误码：UNAUTHENTICATED
- specs/health-services-platform/tasks.md -> 阶段3-15.2

说明：
- v1 最小可执行：仅支持 HS256（与 .env.example 默认一致）。
- token payload 不作为对外契约，仅保证服务端可解码并定位 userId。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import HTTPException

from app.utils.settings import settings


def create_user_token(*, user_id: str, channel: str = "H5") -> str:
    now = datetime.now(tz=UTC)
    jti = str(uuid4())
    payload = {
        "sub": user_id,
        "actorType": "USER",
        "channel": channel,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_expire_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_and_validate_user_token(*, token: str, require_channel: str | None = None) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 已过期"}) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 无效"}) from exc

    if payload.get("actorType") != "USER" or not payload.get("sub") or not payload.get("jti"):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 无效"})

    if require_channel is not None and payload.get("channel") != require_channel:
        # 防串用：小程序接口拒绝 H5 token 等
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Token 无效"})

    return payload


def token_blacklist_key(*, jti: str) -> str:
    """USER token 黑名单 key（REQ-P0-002）。"""

    return f"token:blacklist:{jti}"
