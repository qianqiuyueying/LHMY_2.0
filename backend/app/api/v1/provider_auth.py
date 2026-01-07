"""Provider 认证（v1 最小可执行）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段12「Provider 认证（v1）」
- specs/health-services-platform/design.md -> RBAC：PROVIDER/PROVIDER_STAFF
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType
from app.models.provider import Provider
from app.models.provider_staff import ProviderStaff
from app.models.provider_user import ProviderUser
from app.models.venue import Venue
from app.services.password_hashing import hash_password, verify_password
from app.services.sms_code_service import SmsCodeService
from app.utils.db import get_session_factory
from app.utils.jwt_provider_token import create_provider_token, decode_and_validate_provider_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso
from app.utils.settings import settings
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["provider-auth"])

# 登录失败锁定（与 admin 登录页“剩余时间提示”口径对齐）
_LOGIN_FAIL_WINDOW_SECONDS = 10 * 60
_LOGIN_FAIL_MAX = 5
_LOGIN_LOCK_SECONDS = 30 * 60


def _login_fail_key(username: str) -> str:
    return f"provider:login:fail:{username.strip().lower()}"


def _login_lock_key(username: str) -> str:
    return f"provider:login:lock:{username.strip().lower()}"


async def _raise_if_login_locked(*, redis, username: str) -> None:
    key = _login_lock_key(username)
    if await redis.exists(key):
        ttl = int(await redis.ttl(key) or 0)
        retry_after_seconds = ttl if ttl > 0 else int(_LOGIN_LOCK_SECONDS)
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RATE_LIMITED",
                "message": "登录失败次数过多，请稍后重试",
                "details": {"retryAfterSeconds": retry_after_seconds},
            },
        )


async def _record_login_failure(*, redis, username: str) -> None:
    key = _login_fail_key(username)
    n = int(await redis.incr(key))
    if n == 1:
        await redis.expire(key, _LOGIN_FAIL_WINDOW_SECONDS)
    if n >= _LOGIN_FAIL_MAX:
        await redis.set(_login_lock_key(username), "1", ex=_LOGIN_LOCK_SECONDS)
        await redis.delete(key)

async def _require_provider_context(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_provider_token(token=token)
    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return payload


async def _ensure_provider_seed(session) -> None:
    """确保 provider 初始账号存在（开发/测试环境最小可执行）。

    触发条件：仅当环境变量提供了 provider_init_username/provider_init_password 才会创建。
    """

    username = settings.provider_init_username.strip()
    password = settings.provider_init_password.strip()
    if not username or not password:
        return

    existing = (await session.scalars(select(ProviderUser).where(ProviderUser.username == username).limit(1))).first()
    if existing is not None:
        return

    provider_id = str(uuid4())
    provider_name = settings.provider_init_provider_name.strip() or username

    session.add(Provider(id=provider_id, name=provider_name))
    session.add(
        ProviderUser(
            id=str(uuid4()),
            provider_id=provider_id,
            username=username,
            password_hash=hash_password(password=password),
            status="ACTIVE",
        )
    )
    await session.commit()


async def _ensure_provider_staff_seed(session) -> None:
    """确保 provider_staff 初始账号存在（可选）。"""

    username = settings.provider_staff_init_username.strip()
    password = settings.provider_staff_init_password.strip()
    if not username or not password:
        return

    existing = (await session.scalars(select(ProviderStaff).where(ProviderStaff.username == username).limit(1))).first()
    if existing is not None:
        return

    # 若 provider_init 已配置且已创建，则复用其 provider；否则创建一个新的 Provider
    provider = None
    piu = settings.provider_init_username.strip()
    if piu:
        pu = (await session.scalars(select(ProviderUser).where(ProviderUser.username == piu).limit(1))).first()
        if pu is not None:
            provider = (await session.scalars(select(Provider).where(Provider.id == pu.provider_id).limit(1))).first()

    provider_id = provider.id if provider is not None else str(uuid4())
    if provider is None:
        session.add(Provider(id=provider_id, name=settings.provider_init_provider_name.strip() or "provider"))

    session.add(
        ProviderStaff(
            id=str(uuid4()),
            provider_id=provider_id,
            username=username,
            password_hash=hash_password(password=password),
            status="ACTIVE",
        )
    )
    await session.commit()


class ProviderLoginBody(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/provider/auth/login")
async def provider_login(request: Request, body: ProviderLoginBody):
    username = body.username.strip()
    password = body.password
    if not username:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "用户名或密码错误"})

    redis = get_redis()
    await _raise_if_login_locked(redis=redis, username=username)

    session_factory = get_session_factory()
    async with session_factory() as session:
        await _ensure_provider_seed(session)
        await _ensure_provider_staff_seed(session)

        # 先尝试 PROVIDER
        pu = (await session.scalars(select(ProviderUser).where(ProviderUser.username == username).limit(1))).first()
        if pu is not None and verify_password(password=password, password_hash=pu.password_hash):
            if str(pu.status or "").upper() == "PENDING_REVIEW":
                raise HTTPException(
                    status_code=403,
                    detail={"code": "ACCOUNT_PENDING_REVIEW", "message": "账号待审核，请联系管理员启用后再登录"},
                )
            if str(pu.status or "").upper() != "ACTIVE":
                raise HTTPException(status_code=403, detail={"code": "ACCOUNT_SUSPENDED", "message": "账号已冻结"})

            # 登录成功：清理失败计数/锁定
            await redis.delete(_login_fail_key(username))
            await redis.delete(_login_lock_key(username))

            token, _jti = create_provider_token(actor_type="PROVIDER", actor_id=pu.id)
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.PROVIDER.value,
                    actor_id=pu.id,
                    action=AuditAction.LOGIN.value,
                    resource_type="PROVIDER_AUTH",
                    resource_id=pu.id,
                    summary="PROVIDER 登录",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={
                        "path": request.url.path,
                        "method": request.method,
                        "requestId": request.state.request_id,
                    },
                )
            )
            await session.commit()
            return ok(
                data={
                    "token": token,
                    "actor": {
                        "id": pu.id,
                        "username": pu.username,
                        "actorType": "PROVIDER",
                        "providerId": pu.provider_id,
                    },
                },
                request_id=request.state.request_id,
            )

        # 再尝试 PROVIDER_STAFF
        ps = (await session.scalars(select(ProviderStaff).where(ProviderStaff.username == username).limit(1))).first()
        if (
            ps is not None
            and ps.status == "ACTIVE"
            and verify_password(password=password, password_hash=ps.password_hash)
        ):
            # 登录成功：清理失败计数/锁定
            await redis.delete(_login_fail_key(username))
            await redis.delete(_login_lock_key(username))

            token, _jti = create_provider_token(actor_type="PROVIDER_STAFF", actor_id=ps.id)
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.PROVIDER_STAFF.value,
                    actor_id=ps.id,
                    action=AuditAction.LOGIN.value,
                    resource_type="PROVIDER_AUTH",
                    resource_id=ps.id,
                    summary="PROVIDER_STAFF 登录",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={
                        "path": request.url.path,
                        "method": request.method,
                        "requestId": request.state.request_id,
                    },
                )
            )
            await session.commit()
            return ok(
                data={
                    "token": token,
                    "actor": {
                        "id": ps.id,
                        "username": ps.username,
                        "actorType": "PROVIDER_STAFF",
                        "providerId": ps.provider_id,
                    },
                },
                request_id=request.state.request_id,
            )

    await _record_login_failure(redis=redis, username=username)
    raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "用户名或密码错误"})


class ProviderRegisterChallengeBody(BaseModel):
    phone: str = Field(..., min_length=1, max_length=32)


@router.post("/provider/auth/register/challenge")
async def provider_register_challenge(request: Request, body: ProviderRegisterChallengeBody):
    service = SmsCodeService(get_redis())
    result = await service.request_code(phone=str(body.phone).strip(), scene="PROVIDER_REGISTER")
    return ok(
        data={
            "sent": result.sent,
            "expiresInSeconds": result.expires_in_seconds,
            "resendAfterSeconds": result.resend_after_seconds,
        },
        request_id=request.state.request_id,
    )


class ProviderRegisterBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    providerName: str = Field(..., min_length=1, max_length=256)
    phone: str = Field(..., min_length=1, max_length=32)
    smsCode: str = Field(..., min_length=4, max_length=10)


@router.post("/provider/auth/register")
async def provider_register(request: Request, body: ProviderRegisterBody):
    username = str(body.username or "").strip()
    provider_name = str(body.providerName or "").strip()
    phone = str(body.phone or "").strip()
    sms_code = str(body.smsCode or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "username 不能为空"})
    if not provider_name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "providerName 不能为空"})

    # 短信校验（复用 service；注册场景）
    service = SmsCodeService(get_redis())
    await service.verify_code(phone=phone, scene="PROVIDER_REGISTER", sms_code=sms_code)

    session_factory = get_session_factory()
    async with session_factory() as session:
        existing_user = (await session.scalars(select(ProviderUser).where(ProviderUser.username == username).limit(1))).first()
        if existing_user is not None:
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "username 已存在"})
        existing_staff = (await session.scalars(select(ProviderStaff).where(ProviderStaff.username == username).limit(1))).first()
        if existing_staff is not None:
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "username 已存在"})

        # 规格：provider_users.phone 角色内唯一（provider 域内）
        if phone:
            existing_phone = (
                await session.scalars(select(ProviderUser).where(ProviderUser.phone == phone).limit(1))
            ).first()
            if existing_phone is not None:
                raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "手机号已注册"})

        provider_id = str(uuid4())
        user_id = str(uuid4())
        now = datetime.now(tz=UTC).replace(tzinfo=None)

        session.add(Provider(id=provider_id, name=provider_name))
        session.add(
            Venue(
                id=str(uuid4()),
                provider_id=provider_id,
                name=provider_name,
            )
        )
        session.add(
            ProviderUser(
                id=user_id,
                provider_id=provider_id,
                username=username,
                password_hash=hash_password(password=str(body.password or "")),
                status="PENDING_REVIEW",
                phone=phone or None,
            )
        )
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.PROVIDER.value,
                actor_id=user_id,
                action=AuditAction.CREATE.value,
                resource_type="PROVIDER_USER",
                resource_id=user_id,
                summary=f"PROVIDER 注册提交：{username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "providerId": provider_id,
                    "providerName": provider_name,
                    "username": username,
                    "submittedAt": _iso(now),
                },
            )
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            # 并发/竞态兜底：username/phone 唯一索引冲突
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "资源已存在"}) from exc

    return ok(data={"submitted": True}, request_id=request.state.request_id)


@router.post("/provider/auth/refresh")
async def provider_refresh(request: Request, authorization: str | None = Header(default=None)):
    """刷新 provider token（REQ-P2-003）。"""

    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_provider_token(token=token)

    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})

    exp = int(payload.get("exp", 0))
    now = int(datetime.now(tz=UTC).timestamp())
    ttl = max(1, exp - now)
    await redis.set(token_blacklist_key(jti=str(payload["jti"])), "1", ex=ttl)

    new_token, _new_jti = create_provider_token(actor_type=str(payload["actorType"]), actor_id=str(payload["sub"]))
    return ok(data={"token": new_token}, request_id=request.state.request_id)


class ProviderChangePasswordBody(BaseModel):
    oldPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8)


@router.post("/provider/auth/change-password")
async def provider_change_password(
    request: Request,
    body: ProviderChangePasswordBody,
    authorization: str | None = Header(default=None),
):
    payload = await _require_provider_context(authorization)
    actor_type = str(payload.get("actorType"))
    actor_id = str(payload.get("sub"))

    old_pwd = str(body.oldPassword or "")
    new_pwd = str(body.newPassword or "")
    if len(new_pwd) < 8:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "新密码长度至少为 8 位"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        if actor_type == "PROVIDER":
            u = (await session.scalars(select(ProviderUser).where(ProviderUser.id == actor_id).limit(1))).first()
            if u is None or u.status != "ACTIVE":
                raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
            if not verify_password(password=old_pwd, password_hash=u.password_hash):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "旧密码错误"})
            u.password_hash = hash_password(password=new_pwd)
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.PROVIDER.value,
                    actor_id=u.id,
                    action=AuditAction.UPDATE.value,
                    resource_type="PROVIDER_AUTH",
                    resource_id=u.id,
                    summary="PROVIDER 修改密码",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={"path": request.url.path, "method": request.method, "requestId": request.state.request_id},
                )
            )
            await session.commit()
            return ok(data={"ok": True}, request_id=request.state.request_id)

        if actor_type == "PROVIDER_STAFF":
            u = (await session.scalars(select(ProviderStaff).where(ProviderStaff.id == actor_id).limit(1))).first()
            if u is None or u.status != "ACTIVE":
                raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
            if not verify_password(password=old_pwd, password_hash=u.password_hash):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "旧密码错误"})
            u.password_hash = hash_password(password=new_pwd)
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.PROVIDER_STAFF.value,
                    actor_id=u.id,
                    action=AuditAction.UPDATE.value,
                    resource_type="PROVIDER_AUTH",
                    resource_id=u.id,
                    summary="PROVIDER_STAFF 修改密码",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={"path": request.url.path, "method": request.method, "requestId": request.state.request_id},
                )
            )
            await session.commit()
            return ok(data={"ok": True}, request_id=request.state.request_id)

    raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})


@router.post("/provider/auth/logout")
async def provider_logout(request: Request, authorization: str | None = Header(default=None)):
    """provider 登出（REQ-P2-003）。"""

    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_provider_token(token=token)

    exp = int(payload.get("exp", 0))
    now = int(datetime.now(tz=UTC).timestamp())
    ttl = max(1, exp - now)

    redis = get_redis()
    await redis.set(token_blacklist_key(jti=str(payload["jti"])), "1", ex=ttl)
    return ok(data={"success": True}, request_id=request.state.request_id)
