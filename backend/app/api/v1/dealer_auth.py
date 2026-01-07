"""Dealer 认证（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> RBAC：DEALER

说明（v1）：
- 当前系统无注册入口：通过环境变量提供“可重复获取账号”的路径（种子账号）。
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.dealer import Dealer
from app.models.dealer_user import DealerUser
from app.models.enums import DealerStatus
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType
from app.services.password_hashing import hash_password, verify_password
from app.services.sms_code_service import SmsCodeService
from app.utils.db import get_session_factory
from app.utils.jwt_dealer_token import create_dealer_token, decode_and_validate_dealer_token
from app.utils.redis_client import get_redis
from app.utils.response import ok
from app.utils.settings import settings
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["dealer-auth"])

# 登录失败锁定（与 admin 登录页“剩余时间提示”口径对齐）
_LOGIN_FAIL_WINDOW_SECONDS = 10 * 60
_LOGIN_FAIL_MAX = 5
_LOGIN_LOCK_SECONDS = 30 * 60


def _login_fail_key(username: str) -> str:
    return f"dealer:login:fail:{username.strip().lower()}"


def _login_lock_key(username: str) -> str:
    return f"dealer:login:lock:{username.strip().lower()}"


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


async def _ensure_dealer_seed(session) -> None:
    username = settings.dealer_init_username.strip()
    password = settings.dealer_init_password.strip()
    if not username or not password:
        return

    existing = (await session.scalars(select(DealerUser).where(DealerUser.username == username).limit(1))).first()
    if existing is not None:
        return

    dealer_id = str(uuid4())
    dealer_name = settings.dealer_init_dealer_name.strip() or username

    session.add(Dealer(id=dealer_id, name=dealer_name, status=DealerStatus.ACTIVE.value))
    session.add(
        DealerUser(
            id=str(uuid4()),
            dealer_id=dealer_id,
            username=username,
            password_hash=hash_password(password=password),
            status="ACTIVE",
        )
    )
    await session.commit()


class DealerLoginBody(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/dealer/auth/login")
async def dealer_login(request: Request, body: DealerLoginBody):
    username = body.username.strip()
    password = body.password
    if not username:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "用户名或密码错误"})

    redis = get_redis()
    await _raise_if_login_locked(redis=redis, username=username)

    session_factory = get_session_factory()
    async with session_factory() as session:
        await _ensure_dealer_seed(session)

        du = (await session.scalars(select(DealerUser).where(DealerUser.username == username).limit(1))).first()
        if du is None or not verify_password(password=password, password_hash=du.password_hash):
            await _record_login_failure(redis=redis, username=username)
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "用户名或密码错误"})
        if str(du.status or "").upper() == "PENDING_REVIEW":
            raise HTTPException(
                status_code=403,
                detail={"code": "ACCOUNT_PENDING_REVIEW", "message": "账号待审核，请联系管理员启用后再登录"},
            )
        if str(du.status or "").upper() != "ACTIVE":
            raise HTTPException(status_code=403, detail={"code": "ACCOUNT_SUSPENDED", "message": "账号已冻结"})

        dealer = (await session.scalars(select(Dealer).where(Dealer.id == du.dealer_id).limit(1))).first()
        if dealer is None:
            await _record_login_failure(redis=redis, username=username)
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "用户名或密码错误"})
        if dealer.status != DealerStatus.ACTIVE.value:
            await _record_login_failure(redis=redis, username=username)
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "经销商已停用"})

        # 登录成功：清理失败计数/锁定
        await redis.delete(_login_fail_key(username))
        await redis.delete(_login_lock_key(username))

        token, _jti = create_dealer_token(actor_id=du.id)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.DEALER.value,
                actor_id=du.id,
                action=AuditAction.LOGIN.value,
                resource_type="DEALER_AUTH",
                resource_id=du.id,
                summary="DEALER 登录",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"path": request.url.path, "method": request.method, "requestId": request.state.request_id},
            )
        )
        await session.commit()

        return ok(
            data={
                "token": token,
                "actor": {"id": du.id, "username": du.username, "actorType": "DEALER", "dealerId": du.dealer_id},
            },
            request_id=request.state.request_id,
        )


class DealerRegisterChallengeBody(BaseModel):
    phone: str = Field(..., min_length=1, max_length=32)


@router.post("/dealer/auth/register/challenge")
async def dealer_register_challenge(request: Request, body: DealerRegisterChallengeBody):
    service = SmsCodeService(get_redis())
    result = await service.request_code(phone=str(body.phone).strip(), scene="DEALER_REGISTER")
    return ok(
        data={
            "sent": result.sent,
            "expiresInSeconds": result.expires_in_seconds,
            "resendAfterSeconds": result.resend_after_seconds,
        },
        request_id=request.state.request_id,
    )


class DealerRegisterBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    dealerName: str = Field(..., min_length=1, max_length=256)
    phone: str = Field(..., min_length=1, max_length=32)
    smsCode: str = Field(..., min_length=4, max_length=10)


@router.post("/dealer/auth/register")
async def dealer_register(request: Request, body: DealerRegisterBody):
    username = str(body.username or "").strip()
    dealer_name = str(body.dealerName or "").strip()
    phone = str(body.phone or "").strip()
    sms_code = str(body.smsCode or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "username 不能为空"})
    if not dealer_name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerName 不能为空"})

    service = SmsCodeService(get_redis())
    await service.verify_code(phone=phone, scene="DEALER_REGISTER", sms_code=sms_code)

    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = (await session.scalars(select(DealerUser).where(DealerUser.username == username).limit(1))).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "username 已存在"})

        # 规格：dealer_users.phone 角色内唯一（dealer 域内）
        if phone:
            existing_phone = (
                await session.scalars(select(DealerUser).where(DealerUser.phone == phone).limit(1))
            ).first()
            if existing_phone is not None:
                raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "手机号已注册"})

        dealer_id = str(uuid4())
        user_id = str(uuid4())
        session.add(Dealer(id=dealer_id, name=dealer_name, status=DealerStatus.ACTIVE.value))
        session.add(
            DealerUser(
                id=user_id,
                dealer_id=dealer_id,
                username=username,
                password_hash=hash_password(password=str(body.password or "")),
                status="PENDING_REVIEW",
                phone=phone or None,
            )
        )
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.DEALER.value,
                actor_id=user_id,
                action=AuditAction.CREATE.value,
                resource_type="DEALER_USER",
                resource_id=user_id,
                summary=f"DEALER 注册提交：{username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "dealerId": dealer_id,
                    "dealerName": dealer_name,
                    "username": username,
                },
            )
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            # 并发/竞态兜底：username/phone 唯一索引冲突
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "资源已存在"}) from exc

    return ok(data={"submitted": True}, request_id=request.state.request_id)


class DealerChangePasswordBody(BaseModel):
    oldPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8)


@router.post("/dealer/auth/change-password")
async def dealer_change_password(
    request: Request,
    body: DealerChangePasswordBody,
    authorization: str | None = Header(default=None),
):
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_dealer_token(token=token)
    dealer_user_id = str(payload.get("sub"))

    old_pwd = str(body.oldPassword or "")
    new_pwd = str(body.newPassword or "")
    if len(new_pwd) < 8:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "新密码长度至少为 8 位"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        du = (await session.scalars(select(DealerUser).where(DealerUser.id == dealer_user_id).limit(1))).first()
        if du is None or du.status != "ACTIVE":
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
        if not verify_password(password=old_pwd, password_hash=du.password_hash):
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "旧密码错误"})

        du.password_hash = hash_password(password=new_pwd)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.DEALER.value,
                actor_id=du.id,
                action=AuditAction.UPDATE.value,
                resource_type="DEALER_AUTH",
                resource_id=du.id,
                summary="DEALER 修改密码",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"path": request.url.path, "method": request.method, "requestId": request.state.request_id},
            )
        )
        await session.commit()

    return ok(data={"ok": True}, request_id=request.state.request_id)

