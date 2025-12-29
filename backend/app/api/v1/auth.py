"""认证与会话（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> A.认证与会话（request-sms-code / auth/login）
- specs/health-services-platform/design.md -> 企业绑定与企业名称智能匹配（bind-enterprise / enterprise-suggestions）
- specs/health-services-platform/design.md -> 短信验证码规则（5min/60s/20次/失败锁定）
- specs/health-services-platform/tasks.md -> 阶段3-14/15
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.models.enterprise import Enterprise
from app.models.enums import UserEnterpriseBindingStatus
from app.models.user import User
from app.models.user_enterprise_binding import UserEnterpriseBinding
from app.services.enterprise_matching import EnterpriseCandidate, normalize_enterprise_name, suggest_enterprises
from app.services.sms_code_service import SmsCodeService
from app.services.user_identity_service import compute_identities_and_member_valid_until
from app.services.enterprise_binding_rules import can_submit_new_binding
from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_token import create_user_token, decode_and_validate_user_token, token_blacklist_key as user_token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["auth"])


class RequestSmsCodeBody(BaseModel):
    phone: str = Field(..., description="手机号（11位，v1 校验中国大陆手机号格式）")
    scene: Literal["H5_BUY", "MP_BIND_PHONE"] = Field(..., description="短信场景")


class RequestSmsCodeResp(BaseModel):
    sent: bool
    expiresInSeconds: int
    resendAfterSeconds: int


@router.post("/auth/request-sms-code")
async def request_sms_code(request: Request, body: RequestSmsCodeBody):
    service = SmsCodeService(get_redis())
    result = await service.request_code(phone=body.phone, scene=body.scene)
    return ok(
        data=RequestSmsCodeResp(
            sent=result.sent,
            expiresInSeconds=result.expires_in_seconds,
            resendAfterSeconds=result.resend_after_seconds,
        ).model_dump(),
        request_id=request.state.request_id,
    )


class H5LoginBody(BaseModel):
    channel: Literal["H5"] = Field("H5", description="登录渠道（v1 仅支持 H5）")
    phone: str
    smsCode: str = Field(..., min_length=4, max_length=10)


class H5LoginRespUser(BaseModel):
    id: str
    phone: str
    identities: list[Literal["MEMBER", "EMPLOYEE"]]


class H5LoginResp(BaseModel):
    token: str
    user: H5LoginRespUser


@router.post("/auth/login")
async def h5_login(request: Request, body: H5LoginBody):
    if body.channel != "H5":
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "不支持的登录渠道"})

    # 1) 校验短信验证码（含失败锁定）
    sms_service = SmsCodeService(get_redis())
    await sms_service.verify_code(phone=body.phone, scene="H5_BUY", sms_code=body.smsCode)

    # 2) 以 phone 为主键获取/创建用户（v1：unionid 可为空）
    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(User).where(User.phone == body.phone).limit(1)
        user = (await session.scalars(stmt)).first()
        if user is None:
            user = User(
                id=str(uuid4()),
                phone=body.phone,
                openid=None,
                unionid=None,
                nickname="",
                avatar=None,
                identities=[],
                enterprise_id=None,
                enterprise_name=None,
                binding_time=None,
            )
            session.add(user)

        identities, _member_valid_until = await compute_identities_and_member_valid_until(session=session, user=user)
        user.identities = identities

        await session.commit()

    token = create_user_token(user_id=user.id, channel="H5")
    return ok(
        data=H5LoginResp(
            token=token,
            user=H5LoginRespUser(id=user.id, phone=body.phone, identities=identities),  # type: ignore[arg-type]
        ).model_dump(),
        request_id=request.state.request_id,
    )


class EnterpriseSuggestionRespItem(BaseModel):
    id: str
    name: str
    cityCode: str | None = None


@router.get("/auth/enterprise-suggestions")
async def enterprise_suggestions(request: Request, keyword: str = ""):
    # v1：不强制登录；keyword 为空返回空列表
    session_factory = get_session_factory()
    async with session_factory() as session:
        enterprises = (await session.scalars(select(Enterprise).limit(2000))).all()
        candidates = [EnterpriseCandidate(id=e.id, name=e.name, city_code=e.city_code) for e in enterprises]
        suggestions = suggest_enterprises(keyword=keyword, enterprises=candidates, limit=10)

    return ok(
        data={
            "items": [
                EnterpriseSuggestionRespItem(id=s.id, name=s.name, cityCode=s.city_code).model_dump()
                for s in suggestions
            ]
        },
        request_id=request.state.request_id,
    )


def _extract_user_id_from_request(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    token = auth.split(" ", 1)[1].strip()
    payload = decode_and_validate_user_token(token=token)
    return str(payload["sub"])


class BindEnterpriseBody(BaseModel):
    enterpriseName: str = Field(..., min_length=1)
    enterpriseId: str | None = None
    # v1：城市信息由用户在小程序绑定流程中“明确选择”提供；后端不做推断
    cityCode: str = Field(..., min_length=1)


@router.post("/auth/bind-enterprise")
async def bind_enterprise(request: Request, body: BindEnterpriseBody):
    user_id = _extract_user_id_from_request(request)

    enterprise_name = body.enterpriseName.strip()
    if not enterprise_name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "enterpriseName 不能为空"})

    city_code = str(body.cityCode or "").strip()
    if not city_code:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "cityCode 不能为空"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 绑定唯一性：存在 APPROVED 则拒绝
        bindings = (
            await session.scalars(select(UserEnterpriseBinding).where(UserEnterpriseBinding.user_id == user_id))
        ).all()
        existing_statuses: list[UserEnterpriseBindingStatus] = []
        for b in bindings:
            try:
                existing_statuses.append(UserEnterpriseBindingStatus(b.status))
            except Exception:
                # 遇到未知状态：保守处理为不允许提交（避免绕过约束）
                raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "绑定状态异常"})

        if not can_submit_new_binding(existing_statuses=existing_statuses):
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "已存在生效的企业绑定"})

        # 选择/创建企业（Property 11：提交即写入）
        enterprise: Enterprise | None = None
        if body.enterpriseId:
            enterprise = (
                await session.scalars(select(Enterprise).where(Enterprise.id == body.enterpriseId).limit(1))
            ).first()
            if enterprise is None:
                raise HTTPException(
                    status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "enterpriseId 无效"}
                )
            # v1：城市信息“只允许首次写入”，避免历史企业城市被随意改写导致口径漂移
            existing_city = str(enterprise.city_code or "").strip()
            if existing_city and existing_city != city_code:
                raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "企业城市信息不一致"})
            if not existing_city:
                enterprise.city_code = city_code
        else:
            # 无 enterpriseId：尝试复用“同名规范化后唯一”的企业
            all_enterprises = (await session.scalars(select(Enterprise))).all()
            normalized_input = normalize_enterprise_name(enterprise_name)
            for e in all_enterprises:
                if normalize_enterprise_name(e.name) == normalized_input:
                    enterprise = e
                    break
            if enterprise is None:
                enterprise = Enterprise(
                    id=str(uuid4()),
                    name=enterprise_name,
                    country_code=None,
                    province_code=None,
                    city_code=city_code,
                    source="USER_FIRST_BINDING",
                    first_seen_at=datetime.utcnow(),
                )
                session.add(enterprise)
            else:
                existing_city = str(enterprise.city_code or "").strip()
                if existing_city and existing_city != city_code:
                    raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "企业城市信息不一致"})
                if not existing_city:
                    enterprise.city_code = city_code

        # 创建绑定记录（PENDING）
        binding = UserEnterpriseBinding(
            id=str(uuid4()),
            user_id=user_id,
            enterprise_id=enterprise.id,
            status="PENDING",
            binding_time=datetime.utcnow(),
        )
        session.add(binding)
        await session.commit()

    return ok(
        data={
            "bindingId": binding.id,
            "status": "PENDING",
            "enterpriseName": enterprise.name,
            "message": "绑定申请已提交，等待审核",
        },
        request_id=request.state.request_id,
    )


# -----------------------------
# Admin：企业绑定审核（阶段10）
# -----------------------------


@router.post("/auth/refresh")
async def user_refresh(request: Request, authorization: str | None = Header(default=None)):
    """刷新 USER token（REQ-P2-002）。

    v1 最小口径：基于现有 access token 续期，并使旧 token 立即失效（blacklist）。
    """

    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token)

    redis = get_redis()
    if await redis.exists(user_token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})

    exp = int(payload.get("exp", 0))
    now = int(datetime.now(tz=UTC).timestamp())
    ttl = max(1, exp - now)
    await redis.set(user_token_blacklist_key(jti=str(payload["jti"])), "1", ex=ttl)

    new_token = create_user_token(user_id=str(payload["sub"]), channel=str(payload.get("channel") or "H5"))
    return ok(data={"token": new_token}, request_id=request.state.request_id)


@router.post("/auth/logout")
async def user_logout(request: Request, authorization: str | None = Header(default=None)):
    """USER 登出（REQ-P0-002）。"""

    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token)

    exp = int(payload.get("exp", 0))
    now = int(datetime.now(tz=UTC).timestamp())
    ttl = max(1, exp - now)

    redis = get_redis()
    await redis.set(user_token_blacklist_key(jti=str(payload["jti"])), "1", ex=ttl)
    return ok(data={"success": True}, request_id=request.state.request_id)


async def _require_admin(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_admin_token(token=token)
    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return payload


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


def _parse_dt(raw: str, *, field_name: str) -> datetime:
    try:
        # 允许 YYYY-MM-DD 或 ISO8601（含时分秒/时区）
        if len(raw) == 10:
            return datetime.fromisoformat(raw + "T00:00:00")
        return datetime.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}
        ) from exc


@router.get("/admin/enterprise-bindings")
async def admin_list_enterprise_bindings(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    status: Literal["PENDING", "APPROVED", "REJECTED"] | None = None,
    phone: str | None = None,
    enterpriseName: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    u = aliased(User)
    e = aliased(Enterprise)

    stmt = (
        select(UserEnterpriseBinding, u.phone, e.name)
        .join(u, u.id == UserEnterpriseBinding.user_id, isouter=True)
        .join(e, e.id == UserEnterpriseBinding.enterprise_id, isouter=True)
    )

    if status:
        stmt = stmt.where(UserEnterpriseBinding.status == str(status))

    if phone and phone.strip():
        stmt = stmt.where(u.phone.like(f"%{phone.strip()}%"))

    if enterpriseName and enterpriseName.strip():
        stmt = stmt.where(e.name.like(f"%{enterpriseName.strip()}%"))

    if dateFrom:
        stmt = stmt.where(UserEnterpriseBinding.binding_time >= _parse_dt(str(dateFrom), field_name="dateFrom"))
    if dateTo:
        stmt = stmt.where(UserEnterpriseBinding.binding_time <= _parse_dt(str(dateTo), field_name="dateTo"))

    stmt = stmt.order_by(UserEnterpriseBinding.binding_time.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items: list[dict] = []
    for b, user_phone, enterprise_name in rows:
        items.append(
            {
                "id": b.id,
                "userId": b.user_id,
                "userPhoneMasked": _mask_phone(user_phone),
                "enterpriseId": b.enterprise_id,
                "enterpriseName": enterprise_name or "",
                "status": b.status,
                "bindingTime": b.binding_time.astimezone().isoformat(),
                "createdAt": b.created_at.astimezone().isoformat(),
                "updatedAt": b.updated_at.astimezone().isoformat(),
            }
        )

    return ok(
        data={"items": items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.put("/admin/enterprise-bindings/{id}/approve")
async def admin_approve_enterprise_binding(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        b = (
            await session.scalars(select(UserEnterpriseBinding).where(UserEnterpriseBinding.id == id).limit(1))
        ).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "绑定关系不存在"})

        # 幂等 no-op：同一目标状态重复提交 -> 200（不刷审计）
        if b.status == UserEnterpriseBindingStatus.APPROVED.value:
            return ok(data={"id": b.id, "status": b.status}, request_id=request.state.request_id)

        # 非法迁移：已 REJECTED 仍 approve
        if b.status != UserEnterpriseBindingStatus.PENDING.value:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "绑定状态不允许审核通过"},
            )

        # 属性10：一旦出现 APPROVED，同一用户新的绑定申请必须被拒绝（防御性校验）
        existing_approved = (
            await session.scalars(
                select(UserEnterpriseBinding)
                .where(
                    UserEnterpriseBinding.user_id == b.user_id,
                    UserEnterpriseBinding.status == UserEnterpriseBindingStatus.APPROVED.value,
                )
                .limit(1)
            )
        ).first()
        if existing_approved is not None:
            raise HTTPException(
                status_code=409, detail={"code": "STATE_CONFLICT", "message": "用户已存在生效的企业绑定"}
            )

        user = (await session.scalars(select(User).where(User.id == b.user_id).limit(1))).first()
        if user is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "用户不存在"})

        enterprise = (
            await session.scalars(select(Enterprise).where(Enterprise.id == b.enterprise_id).limit(1))
        ).first()
        if enterprise is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "企业不存在"})

        # 状态迁移：PENDING -> APPROVED
        before_status = b.status
        b.status = UserEnterpriseBindingStatus.APPROVED.value

        # 生效写入 users（design.md：通过后获得 EMPLOYEE）
        user.enterprise_id = enterprise.id
        user.enterprise_name = enterprise.name
        user.binding_time = datetime.now(tz=UTC)
        identities, _member_valid_until = await compute_identities_and_member_valid_until(session=session, user=user)
        user.identities = identities

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="ENTERPRISE_BINDING_REVIEW",
                resource_id=str(b.id),
                summary="ADMIN 审核通过企业绑定",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "bindingId": str(b.id),
                    "userId": str(b.user_id),
                    "enterpriseId": str(b.enterprise_id),
                    "beforeStatus": str(before_status),
                    "afterStatus": str(b.status),
                },
            )
        )

        await session.commit()
        await session.refresh(b)

    return ok(
        data={"id": b.id, "status": b.status},
        request_id=request.state.request_id,
    )


@router.put("/admin/enterprise-bindings/{id}/reject")
async def admin_reject_enterprise_binding(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        b = (
            await session.scalars(select(UserEnterpriseBinding).where(UserEnterpriseBinding.id == id).limit(1))
        ).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "绑定关系不存在"})

        # 幂等 no-op：同一目标状态重复提交 -> 200（不刷审计）
        if b.status == UserEnterpriseBindingStatus.REJECTED.value:
            return ok(data={"id": b.id, "status": b.status}, request_id=request.state.request_id)

        # 非法迁移：已 APPROVED 仍 reject
        if b.status != UserEnterpriseBindingStatus.PENDING.value:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "绑定状态不允许驳回"},
            )

        # 状态迁移：PENDING -> REJECTED
        before_status = b.status
        b.status = UserEnterpriseBindingStatus.REJECTED.value

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="ENTERPRISE_BINDING_REVIEW",
                resource_id=str(b.id),
                summary="ADMIN 驳回企业绑定",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "bindingId": str(b.id),
                    "userId": str(b.user_id),
                    "enterpriseId": str(b.enterprise_id),
                    "beforeStatus": str(before_status),
                    "afterStatus": str(b.status),
                },
            )
        )

        await session.commit()
        await session.refresh(b)

    return ok(
        data={"id": b.id, "status": b.status},
        request_id=request.state.request_id,
    )
