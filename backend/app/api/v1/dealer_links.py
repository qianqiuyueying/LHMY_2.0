"""经销商链接与参数校验接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> D. 经销商（dealer）：链接/订单/结算
- specs/health-services-platform/design.md -> 经销商参数签名（sign）规则（HMAC-SHA256 / 10分钟）
- specs/health-services-platform/tasks.md -> 阶段7-42/43/44

v1 说明（重要）：
- 规格的 Auth 为 DEALER/ADMIN，但当前代码库尚未实现 DEALER 登录与 token；
  因此 v1 先按 ADMIN 访问（与 provider 侧接口的 v1 口径一致）。
- 由于缺少 dealer 身份上下文，v1 在创建/列表接口中临时要求传入 dealerId（仅用于 ADMIN 场景）。
- “二维码生成”在规格中未给出单独的图片/资源字段；v1 以 `DealerLink.url` 作为二维码 payload，
  前端可直接对该 URL 生成二维码图像。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app.models.audit_log import AuditLog
from app.models.dealer import Dealer
from app.models.dealer_link import DealerLink
from app.models.dealer_user import DealerUser
from app.models.enums import AuditAction, AuditActorType, DealerLinkStatus, DealerStatus
from app.models.sellable_card import SellableCard
from app.services.dealer_signing import sign_params, verify_params
from app.services.idempotency import IdemActorType, IdempotencyCachedResult, IdempotencyService
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_dealer_token import decode_and_validate_dealer_token
from app.utils.redis_client import get_redis
from app.utils.response import fail, ok
from app.utils.settings import settings
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["dealer-links"])

def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not str(idempotency_key).strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return str(idempotency_key).strip()


def _ctx_actor_for_idempotency(ctx: dict) -> tuple[str, str]:
    actor_type = str(ctx.get("actorType") or "")
    if actor_type == "DEALER":
        return ("DEALER", str(ctx.get("dealerUserId") or ctx.get("dealerId") or ""))
    if actor_type == "ADMIN":
        return ("ADMIN", str(ctx.get("adminId") or ""))
    return (actor_type or "UNKNOWN", str(ctx.get("actorId") or ""))


def _ctx_actor_for_audit(ctx: dict) -> tuple[str, str]:
    actor_type = str(ctx.get("actorType") or "")
    if actor_type == "DEALER":
        return (AuditActorType.DEALER.value, str(ctx.get("dealerUserId") or ""))
    if actor_type == "ADMIN":
        return (AuditActorType.ADMIN.value, str(ctx.get("adminId") or ""))
    return (AuditActorType.ADMIN.value, str(ctx.get("actorId") or ""))


async def _idempotency_replay_if_exists(
    *,
    request: Request,
    operation: str,
    actor_type: str,
    actor_id: str,
    idempotency_key: str,
) -> JSONResponse | None:
    idem = IdempotencyService(get_redis())
    cached = await idem.get(
        operation=operation,
        actor_type=cast(IdemActorType, actor_type),
        actor_id=actor_id,
        idempotency_key=idempotency_key,
    )
    if cached is None:
        return None

    if cached.success:
        payload = ok(data=cached.data, request_id=request.state.request_id)
    else:
        err = cached.error or {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "details": None}
        payload = fail(
            code=str(err.get("code", "INTERNAL_ERROR")),
            message=str(err.get("message", "服务器内部错误")),
            details=err.get("details"),
            request_id=request.state.request_id,
        )
    return JSONResponse(status_code=int(cached.status_code), content=payload)


async def _require_admin_context(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_admin_token(token=token)

    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return {"actorType": "ADMIN", "adminId": str(payload["sub"])}


async def _require_dealer_or_admin_context(*, authorization: str | None) -> dict:
    """DEALER/ADMIN 二选一鉴权。

    - DEALER：自动限定 dealerId（不再要求前端手填）
    - ADMIN：允许显式传 dealerId（兼容 v1 管理侧排查/运营代配）
    """

    token = _extract_bearer_token(authorization)
    # 先尝试 dealer token
    try:
        payload = decode_and_validate_dealer_token(token=token)
        actor_id = str(payload["sub"])
        session_factory = get_session_factory()
        async with session_factory() as session:
            du = (
                await session.scalars(select(DealerUser).where(DealerUser.id == actor_id).limit(1))
            ).first()
        if du is None or du.status != "ACTIVE":
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
        return {"actorType": "DEALER", "dealerId": du.dealer_id, "dealerUserId": du.id}
    except HTTPException:
        return await _require_admin_context(authorization)


def _dealer_link_dto(x: DealerLink) -> dict:
    return {
        "id": x.id,
        "dealerId": x.dealer_id,
        "productId": x.product_id,
        "sellableCardId": x.sellable_card_id,
        "campaign": x.campaign,
        "status": x.status,
        "validFrom": x.valid_from.astimezone().isoformat() if x.valid_from else None,
        "validUntil": x.valid_until.astimezone().isoformat() if x.valid_until else None,
        "url": x.url,
        "uv": x.uv,
        "paidCount": x.paid_count,
        "createdAt": x.created_at.astimezone().isoformat(),
        "updatedAt": x.updated_at.astimezone().isoformat(),
    }


async def _apply_expired_status_if_needed(*, session, now: datetime) -> None:
    # v1：用“惰性更新”实现“过期自动处理”（43.3）
    await session.execute(
        update(DealerLink)
        .where(
            DealerLink.status == DealerLinkStatus.ENABLED.value,
            DealerLink.valid_until.is_not(None),
            DealerLink.valid_until < now.replace(tzinfo=None),
        )
        .values(status=DealerLinkStatus.EXPIRED.value, updated_at=datetime.utcnow())
    )


class CreateDealerLinkBody(BaseModel):
    # v1：DEALER 场景自动识别；ADMIN 场景可显式指定
    dealerId: str | None = Field(default=None)

    # v2.1：优先使用 sellableCardId；不再允许手填 productId
    # vNext：允许生成“经销商首页链接”（不指定卡），此时 sellableCardId 为空
    sellableCardId: str | None = Field(default=None)
    campaign: str | None = Field(default=None, max_length=128)
    validFrom: str | None = None  # YYYY-MM-DD
    # v2.2：有效期止必填（避免生成“永久有效”的投放链接导致风控困难）
    validUntil: str | None = None  # YYYY-MM-DD


@router.post("/dealer-links")
async def create_dealer_link(
    request: Request,
    body: CreateDealerLinkBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    ctx = await _require_dealer_or_admin_context(authorization=authorization)
    idem_key = _require_idempotency_key(idempotency_key)
    idem_actor_type, idem_actor_id = _ctx_actor_for_idempotency(ctx)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="create_dealer_link",
        actor_type=idem_actor_type,
        actor_id=idem_actor_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    dealer_id = str(ctx.get("dealerId") or (body.dealerId or "")).strip()
    sellable_card_id_raw = str(body.sellableCardId or "").strip()
    # 关键：不指定卡时必须存 NULL，不能存空字符串，否则 H5 授权/筛选会异常
    sellable_card_id: str | None = sellable_card_id_raw or None

    if not dealer_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ARGUMENT", "message": "dealerId 必填"},
        )

    if not (body.validUntil or "").strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "validUntil 必填"})

    # 解析日期（按 spec：YYYY-MM-DD；存到 datetime（UTC 0点））
    valid_from_dt = None
    valid_until_dt = None
    if body.validFrom:
        try:
            d = datetime.strptime(body.validFrom, "%Y-%m-%d").date()
            valid_from_dt = datetime(d.year, d.month, d.day, tzinfo=UTC)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "validFrom 格式不合法"}
            ) from exc
    if body.validUntil:
        try:
            d = datetime.strptime(body.validUntil, "%Y-%m-%d").date()
            # v1：到期时间取当日 23:59:59（含当天）
            valid_until_dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "validUntil 格式不合法"}
            ) from exc

    # 基础区间校验
    if valid_from_dt and valid_until_dt and valid_from_dt > valid_until_dt:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "validFrom 不可晚于 validUntil"})

    # vNext：投放链接以 dealerLinkId 为主入口（可长期投放）；不再依赖 10 分钟有效的签名参数
    # 说明：签名校验能力仍保留在 /dealer-links/verify（兼容/防篡改属性），但不作为投放链接必须参数。

    session_factory = get_session_factory()
    async with session_factory() as session:
        dealer = (await session.scalars(select(Dealer).where(Dealer.id == dealer_id).limit(1))).first()
        if dealer is None:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不存在"})
        if dealer.status != DealerStatus.ACTIVE.value:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "经销商已停用"})

        # 若指定卡则校验可售卡存在且启用；为空则生成“经销商首页链接”
        if sellable_card_id:
            sc = (
                await session.scalars(select(SellableCard).where(SellableCard.id == sellable_card_id).limit(1))
            ).first()
            if sc is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "sellableCardId 不存在"})
            if sc.status != "ENABLED":
                raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "可售卡已停用"})

        row = DealerLink(
            id=str(uuid4()),
            dealer_id=dealer_id,
            # v2.1：不再依赖商品ID；保留字段为兼容历史模型
            product_id=None,
            sellable_card_id=sellable_card_id,
            campaign=body.campaign.strip() if body.campaign else None,
            status=DealerLinkStatus.ENABLED.value,
            # 统一存 UTC naive（与 now_utc.replace(tzinfo=None) 对齐），避免本地时区导致“提前过期/不可用”
            valid_from=valid_from_dt.replace(tzinfo=None) if valid_from_dt else None,
            valid_until=valid_until_dt.replace(tzinfo=None) if valid_until_dt else None,
            # url 会在插入后根据 dealerLinkId 回填（便于前端直接 copy 投放 URL）
            url="",
            uv=None,
            paid_count=None,
        )
        session.add(row)
        await session.flush()
        row.url = f"/h5?dealerLinkId={row.id}"

        # 业务审计（必做）：创建投放链接
        actor_type, actor_id = _ctx_actor_for_audit(ctx)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=actor_type,
                actor_id=actor_id,
                action=AuditAction.CREATE.value,
                resource_type="DEALER_LINK",
                resource_id=row.id,
                summary=f"创建投放链接：{row.id}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "dealerId": dealer_id,
                    "sellableCardId": sellable_card_id,
                    "campaign": row.campaign,
                    "validFrom": body.validFrom,
                    "validUntil": body.validUntil,
                },
            )
        )
        await session.commit()

    data = _dealer_link_dto(row)

    # 幂等写回：仅缓存“已产生副作用”的结果
    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="create_dealer_link",
        actor_type=cast(IdemActorType, idem_actor_type),
        actor_id=idem_actor_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )

    return ok(data=data, request_id=request.state.request_id)


@router.get("/dealer-links")
async def list_dealer_links(
    request: Request,
    authorization: str | None = Header(default=None),
    dealerId: str | None = None,
    status: Literal["ENABLED", "DISABLED", "EXPIRED"] | None = None,
    sellableCardId: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    ctx = await _require_dealer_or_admin_context(authorization=authorization)

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(DealerLink)

    forced_dealer_id = str(ctx.get("dealerId") or "").strip()
    if forced_dealer_id:
        stmt = stmt.where(DealerLink.dealer_id == forced_dealer_id)
    elif dealerId and dealerId.strip():
        stmt = stmt.where(DealerLink.dealer_id == dealerId.strip())
    if status:
        stmt = stmt.where(DealerLink.status == status)
    if sellableCardId and sellableCardId.strip():
        stmt = stmt.where(DealerLink.sellable_card_id == sellableCardId.strip())

    if dateFrom:
        try:
            df = datetime.strptime(dateFrom, "%Y-%m-%d")
            stmt = stmt.where(DealerLink.created_at >= df)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateFrom 格式不合法"}
            ) from exc
    if dateTo:
        try:
            dt = datetime.strptime(dateTo, "%Y-%m-%d")
            stmt = stmt.where(DealerLink.created_at <= dt)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateTo 格式不合法"}
            ) from exc

    # keyword（v2.1）：匹配 id / dealerId / sellableCardId / campaign / url
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(
            (DealerLink.id.like(kw))
            | (DealerLink.dealer_id.like(kw))
            | (DealerLink.sellable_card_id.like(kw))
            | (DealerLink.campaign.like(kw))
            | (DealerLink.url.like(kw))
        )

    stmt = stmt.order_by(DealerLink.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    now = datetime.now(tz=UTC)
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _apply_expired_status_if_needed(session=session, now=now)
        await session.commit()

        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_dealer_link_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.post("/dealer-links/{id}/disable")
async def disable_dealer_link(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
):
    ctx = await _require_dealer_or_admin_context(authorization=authorization)

    now = datetime.now(tz=UTC)
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _apply_expired_status_if_needed(session=session, now=now)

        row = (await session.scalars(select(DealerLink).where(DealerLink.id == id).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "链接不存在"})

        if ctx.get("actorType") == "DEALER":
            dealer_id = str(ctx.get("dealerId") or "").strip()
            if not dealer_id or row.dealer_id != dealer_id:
                raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权限"})

        # 若已过期则保持 EXPIRED；否则标记 DISABLED
        if row.status in {DealerLinkStatus.DISABLED.value, DealerLinkStatus.EXPIRED.value}:
            # 幂等 no-op：不重复写业务审计
            return ok(data=_dealer_link_dto(row), request_id=request.state.request_id)

        before_status = row.status
        row.status = DealerLinkStatus.DISABLED.value

        actor_type, actor_id = _ctx_actor_for_audit(ctx)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=actor_type,
                actor_id=actor_id,
                action=AuditAction.UPDATE.value,
                resource_type="DEALER_LINK",
                resource_id=row.id,
                summary=f"停用投放链接：{row.id}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "dealerId": row.dealer_id,
                    "beforeStatus": before_status,
                    "afterStatus": DealerLinkStatus.DISABLED.value,
                },
            )
        )
        await session.commit()

    return ok(data=_dealer_link_dto(row), request_id=request.state.request_id)


@router.get("/dealer-links/verify")
async def verify_dealer_params(
    request: Request,
    dealerId: str,
    ts: int,
    nonce: str,
    sign: str,
):
    # 用于 H5 打开/下单前预校验（规格：可选、无 auth）
    now_ts = int(datetime.now(tz=UTC).timestamp())
    res = verify_params(
        secret=settings.dealer_sign_secret,
        dealer_id=str(dealerId),
        ts=int(ts),
        nonce=str(nonce),
        sign=str(sign),
        now_ts=now_ts,
    )
    if not res.ok:
        raise HTTPException(
            status_code=403, detail={"code": res.error_code or "DEALER_SIGN_INVALID", "message": "经销商签名校验失败"}
        )
    return ok(data={"valid": True}, request_id=request.state.request_id)
