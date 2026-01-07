"""经销商侧（dealer）订单与结算接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> D. 经销商（dealer）：链接/订单/结算
- specs/health-services-platform/design.md -> 经销商侧数据范围：仅本 dealer 归属订单/结算
- specs/health-services-platform/tasks.md -> 阶段7-45

v1 说明：
- 当前代码库尚未落地 DEALER 登录与 token，因此 v1 先按 ADMIN 访问；
  并临时要求通过 query 传入 dealerId 来限定数据范围（后续补齐账号体系后移除）。
- dealer 订单默认仅返回健行天下订单：orderType=SERVICE_PACKAGE。
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import aliased

from app.models.audit_log import AuditLog
from app.models.bind_token import BindToken
from app.models.card import Card
from app.models.enums import CardStatus, OrderType, PaymentStatus
from app.models.enums import AuditAction, AuditActorType
from app.models.dealer_settlement_account import DealerSettlementAccount
from app.models.order import Order
from app.models.settlement_record import SettlementRecord
from app.models.user import User
from app.models.dealer_user import DealerUser
from app.models.admin import Admin
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.jwt_dealer_token import decode_and_validate_dealer_token
from app.utils.redis_client import get_redis
from app.utils.response import ok
from uuid import uuid4
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token
from app.utils.datetime_iso import iso as _iso
from app.utils.settings import settings

router = APIRouter(tags=["dealer"])

_TZ_BEIJING = timezone(timedelta(hours=8))


def _parse_beijing_day(raw: str, *, field_name: str) -> date:
    """Parse YYYY-MM-DD from admin date picker. Interpreted as Beijing (UTC+8) natural day."""
    try:
        if len(raw) != 10:
            raise ValueError("expected YYYY-MM-DD")
        return date.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 格式不合法"}) from exc


def _beijing_day_range_to_utc_naive(d: date) -> tuple[datetime, datetime]:
    """Convert Beijing natural day to [start, endExclusive) in naive UTC datetimes (DB stores UTC naive)."""
    start_bj = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    next_day = d + timedelta(days=1)
    end_bj_exclusive = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    return (
        start_bj.astimezone(timezone.utc).replace(tzinfo=None),
        end_bj_exclusive.astimezone(timezone.utc).replace(tzinfo=None),
    )


async def _require_admin_context(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_admin_token(token=token)

    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return {"actorType": "ADMIN", "adminId": str(payload["sub"])}


async def _require_admin_phone_bound(*, admin_id: str) -> None:
    """高风险操作门禁：ADMIN 必须已绑定手机号（用于 2FA）。"""

    session_factory = get_session_factory()
    async with session_factory() as session:
        a = (await session.scalars(select(Admin).where(Admin.id == str(admin_id)).limit(1))).first()
    if a is None or a.status != "ACTIVE":
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    if not (a.phone or "").strip():
        raise HTTPException(status_code=403, detail={"code": "ADMIN_PHONE_REQUIRED", "message": "请先绑定手机号开启2FA"})


async def _require_dealer_or_admin_context(*, authorization: str | None) -> dict:
    """DEALER/ADMIN 二选一鉴权。

    - DEALER：自动限定 dealerId
    - ADMIN：允许通过 query 显式传 dealerId（兼容 v1 管理侧排查）
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
        # 再尝试 admin token
        return await _require_admin_context(authorization)


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


def _mask_reference_last4(ref: str | None) -> str | None:
    if not ref:
        return None
    s = str(ref).strip()
    if len(s) < 4:
        return None
    return s[-4:]


def _sanitize_payout_account(value: object | None) -> dict | None:
    """资金类字段：白名单 + 脱敏（不返回 accountNo/contactPhone 明文）。"""

    if not isinstance(value, dict):
        return None
    v = value
    account_no = v.get("accountNo") or v.get("account_no")
    contact_phone = v.get("contactPhone") or v.get("contact_phone")
    out: dict = {
        "method": v.get("method"),
        "accountName": v.get("accountName") or v.get("account_name"),
        "accountNoMasked": _mask_account_no(str(account_no).strip() if isinstance(account_no, str) else None),
        "bankName": v.get("bankName") or v.get("bank_name"),
        "bankBranch": v.get("bankBranch") or v.get("bank_branch"),
        "contactPhoneMasked": _mask_phone(str(contact_phone).strip() if isinstance(contact_phone, str) else None),
    }
    return out


def _mask_account_no(account_no: str | None) -> str | None:
    if not account_no:
        return None
    s = str(account_no).strip()
    if len(s) <= 8:
        return None
    return f"{s[:4]}****{s[-4:]}"


def _audit_actor(ctx: dict) -> tuple[str, str]:
    if str(ctx.get("actorType")) == "DEALER":
        return (AuditActorType.DEALER.value, str(ctx.get("dealerUserId") or ""))
    return (AuditActorType.ADMIN.value, str(ctx.get("adminId") or ""))


@router.get("/dealer/orders")
async def list_dealer_orders(
    request: Request,
    authorization: str | None = Header(default=None),
    dealerId: str | None = None,
    dealerLinkId: str | None = None,
    orderNo: str | None = None,
    phone: str | None = None,
    paymentStatus: Literal["PENDING", "PAID", "FAILED", "REFUNDED"] | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    ctx = await _require_dealer_or_admin_context(authorization=authorization)
    dealer_id = str(ctx.get("dealerId") or (dealerId or "")).strip()
    if not dealer_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不能为空"})

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    u = aliased(User)
    stmt = select(Order, u.phone).join(u, u.id == Order.user_id, isouter=True)

    # v1：仅返回健行天下订单
    stmt = stmt.where(Order.order_type == OrderType.SERVICE_PACKAGE.value)
    stmt = stmt.where(Order.dealer_id == dealer_id)

    if dealerLinkId and str(dealerLinkId).strip():
        stmt = stmt.where(getattr(Order, "dealer_link_id") == str(dealerLinkId).strip())
    if orderNo and orderNo.strip():
        stmt = stmt.where(Order.id == orderNo.strip())
    if paymentStatus:
        stmt = stmt.where(Order.payment_status == paymentStatus)
    if phone and phone.strip():
        # v1：模糊匹配；返回脱敏后的 buyerPhoneMasked
        stmt = stmt.where(u.phone.like(f"%{phone.strip()}%"))

    if dateFrom:
        d_from = _parse_beijing_day(str(dateFrom), field_name="dateFrom")
        start_utc, _end_exclusive = _beijing_day_range_to_utc_naive(d_from)
        stmt = stmt.where(Order.created_at >= start_utc)
    if dateTo:
        d_to = _parse_beijing_day(str(dateTo), field_name="dateTo")
        _start_utc, end_exclusive = _beijing_day_range_to_utc_naive(d_to)
        stmt = stmt.where(Order.created_at < end_exclusive)

    stmt = stmt.order_by(Order.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    # 预取订单明细与可售卡（用于返回卡片摘要）
    order_ids = [o.id for o, _buyer_phone in rows]
    item_map: dict[str, list] = {}
    card_map: dict[str, SellableCard] = {}
    if order_ids:
        from app.models.order_item import OrderItem  # noqa: WPS433
        from app.models.sellable_card import SellableCard  # noqa: WPS433

        item_map_typed: dict[str, list[OrderItem]] = {}
        async with session_factory() as session:
            order_items: list[OrderItem] = list(
                (await session.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids)))).all()
            )
            for it in order_items:
                item_map_typed.setdefault(it.order_id, []).append(it)

            card_ids = list(
                {
                    str(it.item_id)
                    for it in order_items
                    if str(it.item_type) == "SERVICE_PACKAGE" and str(it.item_id or "").strip()
                }
            )
            if card_ids:
                cards = (await session.scalars(select(SellableCard).where(SellableCard.id.in_(card_ids)))).all()
                card_map = {c.id: c for c in cards}
        item_map = item_map_typed

    items: list[dict] = []
    for o, buyer_phone in rows:
        oi0 = (item_map.get(o.id) or [None])[0]
        sellable = card_map.get(getattr(oi0, "item_id", "") or "")
        items.append(
            {
                "id": o.id,
                "orderNo": o.id,  # spec：v1 口径 orderNo=id
                "userId": o.user_id,
                "buyerPhoneMasked": _mask_phone(buyer_phone),
                "orderType": o.order_type,
                "paymentStatus": o.payment_status,
                "totalAmount": float(o.total_amount),
                "dealerId": o.dealer_id,
                "dealerLinkId": getattr(o, "dealer_link_id", None),
                "sellableCardId": (sellable.id if sellable is not None else None),
                "sellableCardName": (sellable.name if sellable is not None else None),
                "regionLevel": (sellable.region_level if sellable is not None else None),
                "createdAt": _iso(o.created_at),
                "paidAt": _iso(o.paid_at),
            }
        )

    return ok(
        data={"items": items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.get("/dealer/orders/export")
async def export_dealer_orders_csv(
    request: Request,
    authorization: str | None = Header(default=None),
    dealerId: str | None = None,
    dealerLinkId: str | None = None,
    orderNo: str | None = None,
    phone: str | None = None,
    paymentStatus: Literal["PENDING", "PAID", "FAILED", "REFUNDED"] | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
):
    """导出：同步直下 CSV（TTL=0，不落盘）。

    规格来源：specs-prod/admin/security.md#5 + specs-prod/admin/api-contracts.md#10(9)
    约束（你已拍板）：
    - dateFrom/dateTo 必填（不填就禁止导出）
    - maxRows=5000，超限拒绝并提示缩小范围
    """

    ctx = await _require_dealer_or_admin_context(authorization=authorization)
    dealer_id = str(ctx.get("dealerId") or (dealerId or "")).strip()
    if not dealer_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不能为空"})

    if not (dateFrom and str(dateFrom).strip()):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateFrom 必填（YYYY-MM-DD）"})
    if not (dateTo and str(dateTo).strip()):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateTo 必填（YYYY-MM-DD）"})

    d_from = _parse_beijing_day(str(dateFrom), field_name="dateFrom")
    start_utc, _end_exclusive = _beijing_day_range_to_utc_naive(d_from)
    d_to = _parse_beijing_day(str(dateTo), field_name="dateTo")
    _start_utc, end_exclusive = _beijing_day_range_to_utc_naive(d_to)

    # 注意：aliased(User) 必须“只创建一次并复用”，否则会生成 users_1/users_2/users_3 等别名，
    # 导致 join/on clause 引用错别名（MySQL 1054 Unknown column in 'on clause'）。
    u = aliased(User)
    stmt = select(Order, u.phone).select_from(Order).join(u, u.id == Order.user_id, isouter=True)  # type: ignore[arg-type]
    # v1：仅返回健行天下订单
    stmt = stmt.where(Order.order_type == OrderType.SERVICE_PACKAGE.value)
    stmt = stmt.where(Order.dealer_id == dealer_id)
    stmt = stmt.where(Order.created_at >= start_utc)
    stmt = stmt.where(Order.created_at < end_exclusive)

    if dealerLinkId and str(dealerLinkId).strip():
        stmt = stmt.where(getattr(Order, "dealer_link_id") == str(dealerLinkId).strip())
    if orderNo and orderNo.strip():
        stmt = stmt.where(Order.id == orderNo.strip())
    if paymentStatus:
        stmt = stmt.where(Order.payment_status == paymentStatus)
    if phone and phone.strip():
        # 已 join u（isouter=True），这里只追加过滤即可
        stmt = stmt.where(u.phone.like(f"%{phone.strip()}%"))

    stmt = stmt.order_by(Order.created_at.desc()).limit(5001)

    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (await session.execute(stmt)).all()

        if len(rows) > 5000:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_ARGUMENT", "message": "导出行数超过 5000，请缩小日期范围或增加筛选条件"},
            )

        # 复用列表逻辑：预取订单明细与可售卡
        order_ids = [o.id for o, _buyer_phone in rows]
        item_map: dict[str, list] = {}
        card_map: dict[str, "SellableCard"] = {}
        if order_ids:
            from app.models.order_item import OrderItem  # noqa: WPS433
            from app.models.sellable_card import SellableCard  # noqa: WPS433

            items = (await session.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids)))).all()
            for it in items:
                item_map.setdefault(it.order_id, []).append(it)

            card_ids = list(
                {
                    str(it.item_id)
                    for it in items
                    if str(it.item_type) == "SERVICE_PACKAGE" and str(it.item_id or "").strip()
                }
            )
            if card_ids:
                cards = (await session.scalars(select(SellableCard).where(SellableCard.id.in_(card_ids)))).all()
                card_map = {c.id: c for c in cards}

        # CSV 内容
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["订单号", "投放链接ID", "卡片", "区域级别", "手机号", "支付状态", "金额", "创建时间", "支付时间"])

        for o, buyer_phone in rows:
            oi0 = (item_map.get(o.id) or [None])[0]
            sellable = card_map.get(getattr(oi0, "item_id", "") or "")
            writer.writerow(
                [
                    o.id,
                    getattr(o, "dealer_link_id", None) or "",
                    (sellable.name if sellable is not None else "") or "",
                    (sellable.region_level if sellable is not None else "") or "",
                    _mask_phone(buyer_phone) or "",
                    o.payment_status or "",
                    float(o.total_amount or 0.0),
                    _iso(o.created_at) or "",
                    _iso(o.paid_at) or "",
                ]
            )

        actor_type, actor_id = _audit_actor(ctx)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=actor_type,
                actor_id=actor_id,
                action=AuditAction.UPDATE.value,  # v1：不新增 EXPORT 枚举
                resource_type="EXPORT_DEALER_ORDERS",
                resource_id=dealer_id,
                summary=f"导出经销商订单 CSV：dealerId={dealer_id}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "dealerId": dealer_id,
                    "filters": {
                        "dealerLinkId": (str(dealerLinkId).strip() if dealerLinkId else None),
                        "orderNo": (str(orderNo).strip() if orderNo else None),
                        "paymentStatus": str(paymentStatus) if paymentStatus else None,
                        "dateFrom": str(dateFrom),
                        "dateTo": str(dateTo),
                    },
                    "rowCount": int(len(rows)),
                    "maxRows": 5000,
                },
            )
        )
        await session.commit()

    content = "\ufeff" + output.getvalue()
    filename = f"dealer-orders-{dealer_id}-{str(dateFrom)}-{str(dateTo)}.csv"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    }
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=headers)


class RegenerateBindTokenResp(BaseModel):
    orderId: str
    cardId: str
    bindToken: str
    expiresAt: str
    miniProgramPath: str


@router.post("/dealer/orders/{orderId}/bind-token/regenerate")
async def dealer_regenerate_bind_token(
    request: Request,
    orderId: str,
    authorization: str | None = Header(default=None),
):
    """Dealer/Admin：为订单重新生成 bind_token（仅 UNBOUND，滚动作废旧 token）。"""

    ctx = await _require_dealer_or_admin_context(authorization=authorization)
    dealer_id = str(ctx.get("dealerId") or "").strip()
    is_admin = str(ctx.get("actorType")) == "ADMIN"

    oid = str(orderId or "").strip()
    if not oid:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "orderId 不能为空"})

    now = datetime.now(tz=UTC).replace(tzinfo=None)

    session_factory = get_session_factory()
    async with session_factory() as session:
        o = (await session.scalars(select(Order).where(Order.id == oid).limit(1))).first()
        if o is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})

        if not is_admin:
            if not dealer_id:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不能为空"})
            if str(o.dealer_id or "") != dealer_id:
                raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "无权操作该订单"})

        if str(o.payment_status or "") != PaymentStatus.PAID.value:
            raise HTTPException(
                status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单未支付成功，无法生成绑定入口"}
            )

        card_id = oid  # v1：cardId=orderId
        c = (await session.scalars(select(Card).where(Card.id == card_id).limit(1))).first()
        if c is None:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "卡尚未生成，请稍后重试"})

        if str(c.status) != CardStatus.UNBOUND.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "卡已绑定，禁止重新生成绑定入口"})

        # 滚动：作废旧 token（used_at 置值），再生成新 token
        await session.execute(
            update(BindToken)
            .where(BindToken.card_id == card_id, BindToken.used_at.is_(None))
            .values(used_at=now)
        )

        token = uuid4().hex
        expires_at = now + timedelta(seconds=int(settings.bind_token_expire_seconds))
        session.add(BindToken(token=token, card_id=card_id, expires_at=expires_at, used_at=None))
        await session.commit()

    mp_path = f"pages/card/bind-by-token?token={token}"
    return ok(
        data=RegenerateBindTokenResp(
            orderId=oid,
            cardId=card_id,
            bindToken=token,
            expiresAt=expires_at.isoformat(),
            miniProgramPath=mp_path,
        ).model_dump(),
        request_id=request.state.request_id,
    )


@router.get("/dealer/settlements")
async def list_dealer_settlements(
    request: Request,
    authorization: str | None = Header(default=None),
    dealerId: str | None = None,
    cycle: str | None = None,
    status: Literal["PENDING_CONFIRM", "SETTLED", "FROZEN"] | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    ctx = await _require_dealer_or_admin_context(authorization=authorization)
    if str(ctx.get("actorType")) == "ADMIN":
        await _require_admin_phone_bound(admin_id=str(ctx.get("adminId") or ""))
    dealer_id = str(ctx.get("dealerId") or (dealerId or "")).strip()
    if not dealer_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不能为空"})

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(SettlementRecord).where(SettlementRecord.dealer_id == dealer_id)
    if cycle and cycle.strip():
        stmt = stmt.where(SettlementRecord.cycle == cycle.strip())
    if status:
        stmt = stmt.where(SettlementRecord.status == status)

    stmt = stmt.order_by(SettlementRecord.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items = [
        {
            "id": x.id,
            "dealerId": x.dealer_id,
            "cycle": x.cycle,
            "orderCount": int(x.order_count),
            "amount": float(x.amount),
            "status": x.status,
            "createdAt": _iso(x.created_at),
            "settledAt": _iso(x.settled_at),
            "payoutMethod": x.payout_method,
            # 规格（TASK-P0-006）：不返回打款信息明文
            "payoutAccount": _sanitize_payout_account(x.payout_account_json),
            "payoutReferenceLast4": _mask_reference_last4(x.payout_reference),
            "payoutNote": x.payout_note,
            "payoutMarkedAt": _iso(x.payout_marked_at),
        }
        for x in rows
    ]

    return ok(
        data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id
    )


@router.get("/dealer/settlement-account")
async def get_dealer_settlement_account(request: Request, authorization: str | None = Header(default=None), dealerId: str | None = None):
    ctx = await _require_dealer_or_admin_context(authorization=authorization)
    dealer_id = str(ctx.get("dealerId") or (dealerId or "")).strip()
    if not dealer_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不能为空"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (
            await session.scalars(select(DealerSettlementAccount).where(DealerSettlementAccount.dealer_id == dealer_id).limit(1))
        ).first()
    if row is None:
        return ok(
            data={"dealerId": dealer_id, "method": "BANK", "accountName": "", "accountNoMasked": None, "bankName": "", "bankBranch": "", "contactPhone": ""},
            request_id=request.state.request_id,
        )
    return ok(
        data={
            "dealerId": dealer_id,
            "method": row.method,
            "accountName": row.account_name,
            "accountNoMasked": _mask_account_no(row.account_no),
            "bankName": row.bank_name or "",
            "bankBranch": row.bank_branch or "",
            "contactPhone": row.contact_phone or "",
            "updatedAt": _iso(row.updated_at),
        },
        request_id=request.state.request_id,
    )


@router.put("/dealer/settlement-account")
async def put_dealer_settlement_account(
    request: Request,
    authorization: str | None = Header(default=None),
    dealerId: str | None = None,
    method: str | None = None,
    accountName: str | None = None,
    accountNo: str | None = None,
    bankName: str | None = None,
    bankBranch: str | None = None,
    contactPhone: str | None = None,
):
    ctx = await _require_dealer_or_admin_context(authorization=authorization)
    dealer_id = str(ctx.get("dealerId") or (dealerId or "")).strip()
    if not dealer_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不能为空"})

    m = str(method or "BANK").strip().upper()
    if m not in {"BANK", "ALIPAY"}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "method 仅支持 BANK/ALIPAY"})
    an = str(accountName or "").strip()
    no = str(accountNo or "").strip()
    if not an:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "accountName 必填"})
    if not no:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "accountNo 必填"})
    bn = str(bankName or "").strip() if m == "BANK" else ""
    if m == "BANK" and not bn:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "bankName 必填"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (
            await session.scalars(select(DealerSettlementAccount).where(DealerSettlementAccount.dealer_id == dealer_id).limit(1))
        ).first()
        if row is None:
            row = DealerSettlementAccount(
                dealer_id=dealer_id,
                method=m,
                account_name=an,
                account_no=no,
                bank_name=bn or None,
                bank_branch=str(bankBranch or "").strip() or None,
                contact_phone=str(contactPhone or "").strip() or None,
            )
            session.add(row)
        else:
            row.method = m
            row.account_name = an
            row.account_no = no
            row.bank_name = bn or None
            row.bank_branch = str(bankBranch or "").strip() or None
            row.contact_phone = str(contactPhone or "").strip() or None
        await session.commit()
        await session.refresh(row)

    return ok(
        data={
            "dealerId": dealer_id,
            "method": row.method,
            "accountName": row.account_name,
            "accountNoMasked": _mask_account_no(row.account_no),
            "bankName": row.bank_name or "",
            "bankBranch": row.bank_branch or "",
            "contactPhone": row.contact_phone or "",
            "updatedAt": _iso(row.updated_at),
        },
        request_id=request.state.request_id,
    )
