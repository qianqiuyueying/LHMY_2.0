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

from fastapi import APIRouter, Header, HTTPException, Request
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
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_token import create_user_token, decode_and_validate_user_token
from app.utils.redis_client import get_redis
from app.utils.response import ok

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


@router.post("/auth/bind-enterprise")
async def bind_enterprise(request: Request, body: BindEnterpriseBody):
    user_id = _extract_user_id_from_request(request)

    enterprise_name = body.enterpriseName.strip()
    if not enterprise_name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "enterpriseName 不能为空"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 绑定唯一性：存在 APPROVED 则拒绝
        bindings = (await session.scalars(select(UserEnterpriseBinding).where(UserEnterpriseBinding.user_id == user_id))).all()
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
            enterprise = (await session.scalars(select(Enterprise).where(Enterprise.id == body.enterpriseId).limit(1))).first()
            if enterprise is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "enterpriseId 无效"})
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
                    city_code=None,
                    source="USER_FIRST_BINDING",
                    first_seen_at=datetime.utcnow(),
                )
                session.add(enterprise)

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


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return parts[1].strip()


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
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}) from exc


@router.get("/admin/enterprise-bindings")
async def admin_list_enterprise_bindings(
    request: Request,
    authorization: str | None = Header(default=None),
    status: Literal["PENDING", "APPROVED", "REJECTED"] | None = None,
    phone: str | None = None,
    enterpriseName: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    await _require_admin(authorization)

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
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        b = (
            await session.scalars(select(UserEnterpriseBinding).where(UserEnterpriseBinding.id == id).limit(1))
        ).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "绑定关系不存在"})

        if b.status != UserEnterpriseBindingStatus.PENDING.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "绑定状态不允许审核通过"})

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
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "用户已存在生效的企业绑定"})

        user = (await session.scalars(select(User).where(User.id == b.user_id).limit(1))).first()
        if user is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "用户不存在"})

        enterprise = (await session.scalars(select(Enterprise).where(Enterprise.id == b.enterprise_id).limit(1))).first()
        if enterprise is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "企业不存在"})

        # 状态迁移：PENDING -> APPROVED
        b.status = UserEnterpriseBindingStatus.APPROVED.value

        # 生效写入 users（design.md：通过后获得 EMPLOYEE）
        user.enterprise_id = enterprise.id
        user.enterprise_name = enterprise.name
        user.binding_time = datetime.utcnow()
        identities, _member_valid_until = await compute_identities_and_member_valid_until(session=session, user=user)
        user.identities = identities

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
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        b = (
            await session.scalars(select(UserEnterpriseBinding).where(UserEnterpriseBinding.id == id).limit(1))
        ).first()
        if b is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "绑定关系不存在"})

        if b.status != UserEnterpriseBindingStatus.PENDING.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "绑定状态不允许驳回"})

        # 状态迁移：PENDING -> REJECTED
        b.status = UserEnterpriseBindingStatus.REJECTED.value
        await session.commit()
        await session.refresh(b)

    return ok(
        data={"id": b.id, "status": b.status},
        request_id=request.state.request_id,
    )
