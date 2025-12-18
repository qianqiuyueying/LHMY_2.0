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

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.models.enums import OrderType
from app.models.order import Order
from app.models.settlement_record import SettlementRecord
from app.models.user import User
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["dealer"])


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


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


@router.get("/dealer/orders")
async def list_dealer_orders(
    request: Request,
    authorization: str | None = Header(default=None),
    dealerId: str | None = None,
    orderNo: str | None = None,
    phone: str | None = None,
    paymentStatus: Literal["PENDING", "PAID", "FAILED", "REFUNDED"] | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    await _require_admin_context(authorization)

    dealer_id = (dealerId or "").strip()
    if not dealer_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerId 不能为空"})

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    u = aliased(User)
    stmt = select(Order, u.phone).join(u, u.id == Order.user_id, isouter=True)

    # v1：仅返回健行天下订单
    stmt = stmt.where(Order.order_type == OrderType.SERVICE_PACKAGE.value)
    stmt = stmt.where(Order.dealer_id == dealer_id)

    if orderNo and orderNo.strip():
        stmt = stmt.where(Order.id == orderNo.strip())
    if paymentStatus:
        stmt = stmt.where(Order.payment_status == paymentStatus)
    if phone and phone.strip():
        # v1：模糊匹配；返回脱敏后的 buyerPhoneMasked
        stmt = stmt.where(u.phone.like(f"%{phone.strip()}%"))

    if dateFrom:
        try:
            df = datetime.strptime(dateFrom, "%Y-%m-%d")
            stmt = stmt.where(Order.created_at >= df)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateFrom 格式不合法"}) from exc
    if dateTo:
        try:
            dt = datetime.strptime(dateTo, "%Y-%m-%d")
            stmt = stmt.where(Order.created_at <= dt)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dateTo 格式不合法"}) from exc

    stmt = stmt.order_by(Order.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items: list[dict] = []
    for o, buyer_phone in rows:
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
                "createdAt": o.created_at.astimezone().isoformat(),
                "paidAt": o.paid_at.astimezone().isoformat() if o.paid_at else None,
            }
        )

    return ok(
        data={"items": items, "page": page, "pageSize": page_size, "total": total},
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
    await _require_admin_context(authorization)

    dealer_id = (dealerId or "").strip()
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
            "createdAt": x.created_at.astimezone().isoformat(),
            "settledAt": x.settled_at.astimezone().isoformat() if x.settled_at else None,
        }
        for x in rows
    ]

    return ok(data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)

