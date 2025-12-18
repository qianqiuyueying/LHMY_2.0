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
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app.models.dealer import Dealer
from app.models.dealer_link import DealerLink
from app.models.enums import DealerLinkStatus, DealerStatus
from app.services.dealer_signing import sign_params, verify_params
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok
from app.utils.settings import settings

router = APIRouter(tags=["dealer-links"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return parts[1].strip()


async def _require_admin_context(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_admin_token(token=token)

    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return {"actorType": "ADMIN", "adminId": str(payload["sub"])}


def _dealer_link_dto(x: DealerLink) -> dict:
    return {
        "id": x.id,
        "dealerId": x.dealer_id,
        "productId": x.product_id,
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
    # v1 临时：ADMIN 场景必须显式指定 dealerId
    dealerId: str = Field(..., min_length=1)

    productId: str = Field(..., min_length=1)
    campaign: str | None = Field(default=None, max_length=128)
    validFrom: str | None = None  # YYYY-MM-DD
    validUntil: str | None = None  # YYYY-MM-DD


@router.post("/dealer-links")
async def create_dealer_link(
    request: Request,
    body: CreateDealerLinkBody,
    authorization: str | None = Header(default=None),
):
    # v1：仅 ADMIN（DEALER 待账号体系补齐）
    await _require_admin_context(authorization)

    dealer_id = body.dealerId.strip()
    product_id = body.productId.strip()
    if not dealer_id or not product_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId/productId 不能为空"})

    # 解析日期（按 spec：YYYY-MM-DD；存到 datetime（UTC 0点））
    valid_from_dt = None
    valid_until_dt = None
    if body.validFrom:
        try:
            d = datetime.strptime(body.validFrom, "%Y-%m-%d").date()
            valid_from_dt = datetime(d.year, d.month, d.day, tzinfo=UTC)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "validFrom 格式不合法"}) from exc
    if body.validUntil:
        try:
            d = datetime.strptime(body.validUntil, "%Y-%m-%d").date()
            # v1：到期时间取当日 23:59:59（含当天）
            valid_until_dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=UTC)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "validUntil 格式不合法"}) from exc

    now = datetime.now(tz=UTC)
    ts = int(now.timestamp())
    nonce = str(uuid4()).replace("-", "")
    sign = sign_params(secret=settings.dealer_sign_secret, dealer_id=dealer_id, ts=ts, nonce=nonce)

    # v1：URL 以相对路径作为“可投放示例/模板”
    url = f"/h5/buy?dealerId={dealer_id}&ts={ts}&nonce={nonce}&sign={sign}"

    session_factory = get_session_factory()
    async with session_factory() as session:
        dealer = (await session.scalars(select(Dealer).where(Dealer.id == dealer_id).limit(1))).first()
        if dealer is None:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不存在"})
        if dealer.status != DealerStatus.ACTIVE.value:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "经销商已停用"})

        row = DealerLink(
            id=str(uuid4()),
            dealer_id=dealer_id,
            product_id=product_id,
            campaign=body.campaign.strip() if body.campaign else None,
            status=DealerLinkStatus.ENABLED.value,
            valid_from=valid_from_dt.astimezone().replace(tzinfo=None) if valid_from_dt else None,
            valid_until=valid_until_dt.astimezone().replace(tzinfo=None) if valid_until_dt else None,
            url=url,
            uv=None,
            paid_count=None,
        )
        session.add(row)
        await session.commit()

    return ok(data=_dealer_link_dto(row), request_id=request.state.request_id)


@router.get("/dealer-links")
async def list_dealer_links(
    request: Request,
    authorization: str | None = Header(default=None),
    dealerId: str | None = None,
    status: Literal["ENABLED", "DISABLED", "EXPIRED"] | None = None,
    productId: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    # v1：仅 ADMIN（DEALER 待账号体系补齐）
    await _require_admin_context(authorization)

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(DealerLink)

    if dealerId and dealerId.strip():
        stmt = stmt.where(DealerLink.dealer_id == dealerId.strip())
    if status:
        stmt = stmt.where(DealerLink.status == status)
    if productId and productId.strip():
        stmt = stmt.where(DealerLink.product_id == productId.strip())

    if dateFrom:
        try:
            df = datetime.strptime(dateFrom, "%Y-%m-%d")
            stmt = stmt.where(DealerLink.created_at >= df)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateFrom 格式不合法"}) from exc
    if dateTo:
        try:
            dt = datetime.strptime(dateTo, "%Y-%m-%d")
            stmt = stmt.where(DealerLink.created_at <= dt)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateTo 格式不合法"}) from exc

    # keyword（v1 最小）：匹配 id / dealerId / productId / campaign / url
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(
            (DealerLink.id.like(kw))
            | (DealerLink.dealer_id.like(kw))
            | (DealerLink.product_id.like(kw))
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
    # v1：仅 ADMIN（DEALER 待账号体系补齐）
    await _require_admin_context(authorization)

    now = datetime.now(tz=UTC)
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _apply_expired_status_if_needed(session=session, now=now)

        row = (await session.scalars(select(DealerLink).where(DealerLink.id == id).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "链接不存在"})

        # 若已过期则保持 EXPIRED；否则标记 DISABLED
        if row.status != DealerLinkStatus.EXPIRED.value:
            row.status = DealerLinkStatus.DISABLED.value
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
        raise HTTPException(status_code=403, detail={"code": res.error_code or "DEALER_SIGN_INVALID", "message": "经销商签名校验失败"})
    return ok(data={"valid": True}, request_id=request.state.request_id)

