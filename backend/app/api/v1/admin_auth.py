"""Admin 认证（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> admin 认证（登录/2FA/refresh/logout + blacklist）
- specs/health-services-platform/tasks.md -> 阶段3-17
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType
from app.services.password_hashing import hash_password, verify_password
from app.services.sms_code_service import SmsCodeService
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import create_admin_token, decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok
from app.utils.settings import settings

router = APIRouter(tags=["admin-auth"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return parts[1].strip()


async def _ensure_admin_seed(session) -> None:
    """按规格：首次启动（v1 开发/测试）若不存在则创建初始账号。"""

    username = settings.admin_init_username.strip()
    password = settings.admin_init_password.strip()
    if not username or not password:
        return

    existing = (await session.scalars(select(Admin).where(Admin.username == username).limit(1))).first()
    if existing is not None:
        return

    session.add(
        Admin(
            id=str(uuid4()),
            username=username,
            password_hash=hash_password(password=password),
            status="ACTIVE",
            phone=None,
        )
    )
    await session.commit()


class AdminLoginBody(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/admin/auth/login")
async def admin_login(request: Request, body: AdminLoginBody):
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _ensure_admin_seed(session)

        admin = (await session.scalars(select(Admin).where(Admin.username == body.username).limit(1))).first()
        if admin is None or not verify_password(password=body.password, password_hash=admin.password_hash):
            raise HTTPException(status_code=401, detail={"code": "ADMIN_CREDENTIALS_INVALID", "message": "用户名或密码错误"})

        if admin.status != "ACTIVE":
            raise HTTPException(status_code=401, detail={"code": "ADMIN_CREDENTIALS_INVALID", "message": "用户名或密码错误"})

        # v1：若 admin 配置了 phone，则视为开启 2FA（按规格“可选”）
        if admin.phone:
            challenge_id = str(uuid4())
            key = f"admin:2fa:challenge:{challenge_id}"
            value = {
                "admin_id": admin.id,
                "phone": admin.phone,
                "created_at": int(datetime.now(tz=UTC).timestamp()),
            }
            redis = get_redis()
            await redis.set(key, json.dumps(value, ensure_ascii=False), ex=10 * 60)
            return ok(
                data={"requires2fa": True, "challengeId": challenge_id},
                request_id=request.state.request_id,
            )

        token, _jti = create_admin_token(admin_id=admin.id)

        # 审计：LOGIN（v1 最小可执行）
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin.id,
                action=AuditAction.LOGIN.value,
                resource_type="ADMIN_AUTH",
                resource_id=admin.id,
                summary="ADMIN 登录",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"path": request.url.path, "method": request.method, "requestId": request.state.request_id},
            )
        )
        await session.commit()

        return ok(
            data={"token": token, "admin": {"id": admin.id, "username": admin.username}},
            request_id=request.state.request_id,
        )


class Admin2faChallengeBody(BaseModel):
    challengeId: str


@router.post("/admin/auth/2fa/challenge")
async def admin_2fa_challenge(request: Request, body: Admin2faChallengeBody):
    redis = get_redis()
    key = f"admin:2fa:challenge:{body.challengeId}"
    raw = await redis.get(key)
    if raw is None:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "challengeId 无效"})

    try:
        payload = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "challengeId 无效"}) from exc

    phone = payload.get("phone")
    if not phone:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "challengeId 无效"})

    service = SmsCodeService(redis)
    result = await service.request_code(phone=str(phone), scene="ADMIN_2FA")
    return ok(
        data={
            "sent": result.sent,
            "expiresInSeconds": result.expires_in_seconds,
            "resendAfterSeconds": result.resend_after_seconds,
        },
        request_id=request.state.request_id,
    )


class Admin2faVerifyBody(BaseModel):
    challengeId: str
    smsCode: str = Field(..., min_length=4, max_length=10)


@router.post("/admin/auth/2fa/verify")
async def admin_2fa_verify(request: Request, body: Admin2faVerifyBody):
    redis = get_redis()
    key = f"admin:2fa:challenge:{body.challengeId}"
    raw = await redis.get(key)
    if raw is None:
        raise HTTPException(status_code=400, detail={"code": "ADMIN_2FA_EXPIRED", "message": "2FA 已过期"})

    payload = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw))
    admin_id = payload.get("admin_id")
    phone = payload.get("phone")
    if not admin_id or not phone:
        raise HTTPException(status_code=400, detail={"code": "ADMIN_2FA_EXPIRED", "message": "2FA 已过期"})

    # 校验短信验证码；将 SMS_CODE_* 映射为 ADMIN_2FA_*
    service = SmsCodeService(redis)
    try:
        await service.verify_code(phone=str(phone), scene="ADMIN_2FA", sms_code=body.smsCode)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = detail.get("code")
        if exc.status_code == 400 and code == "SMS_CODE_INVALID":
            raise HTTPException(status_code=400, detail={"code": "ADMIN_2FA_INVALID", "message": "2FA 验证失败"}) from exc
        if exc.status_code == 400 and code == "SMS_CODE_EXPIRED":
            raise HTTPException(status_code=400, detail={"code": "ADMIN_2FA_EXPIRED", "message": "2FA 已过期"}) from exc
        raise

    # 成功后：challengeId 失效（TTL 过期或已使用）
    await redis.delete(key)

    session_factory = get_session_factory()
    async with session_factory() as session:
        admin = (await session.scalars(select(Admin).where(Admin.id == str(admin_id)).limit(1))).first()
        if admin is None or admin.status != "ACTIVE":
            raise HTTPException(status_code=401, detail={"code": "ADMIN_CREDENTIALS_INVALID", "message": "用户名或密码错误"})

        # 审计：LOGIN（2FA 通过后）
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(admin_id),
                action=AuditAction.LOGIN.value,
                resource_type="ADMIN_AUTH",
                resource_id=str(admin_id),
                summary="ADMIN 登录（2FA）",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"path": request.url.path, "method": request.method, "requestId": request.state.request_id},
            )
        )
        await session.commit()

    token, _jti = create_admin_token(admin_id=str(admin_id))
    return ok(
        data={"token": token, "admin": {"id": admin.id, "username": admin.username}},
        request_id=request.state.request_id,
    )


@router.post("/admin/auth/refresh")
async def admin_refresh(request: Request, authorization: str | None = Header(default=None)):
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_admin_token(token=token)

    redis = get_redis()
    # blacklist 校验（请求阶段）
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})

    # v1 最小：基于现有 access token 续期，并使旧 token 立即失效（blacklist）
    exp = int(payload.get("exp", 0))
    now = int(datetime.now(tz=UTC).timestamp())
    ttl = max(1, exp - now)
    await redis.set(token_blacklist_key(jti=str(payload["jti"])), "1", ex=ttl)

    new_token, _new_jti = create_admin_token(admin_id=str(payload["sub"]))
    return ok(data={"token": new_token}, request_id=request.state.request_id)


@router.post("/admin/auth/logout")
async def admin_logout(request: Request, authorization: str | None = Header(default=None)):
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_admin_token(token=token)

    exp = int(payload.get("exp", 0))
    now = int(datetime.now(tz=UTC).timestamp())
    ttl = max(1, exp - now)

    redis = get_redis()
    await redis.set(token_blacklist_key(jti=str(payload["jti"])), "1", ex=ttl)

    # 审计：LOGOUT（登出）
    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(payload["sub"]),
                action=AuditAction.LOGOUT.value,
                resource_type="ADMIN_AUTH",
                resource_id=str(payload["sub"]),
                summary="ADMIN 登出",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"path": request.url.path, "method": request.method, "requestId": request.state.request_id},
            )
        )
        await session.commit()

    return ok(data={"success": True}, request_id=request.state.request_id)

