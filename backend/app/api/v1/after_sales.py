"""售后与退款接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> AfterSaleCase/Refund 模型
- specs/health-services-platform/design.md -> E-2 admin 售后仲裁 decide（v1 最小契约）
- specs/health-services-platform/design.md -> 属性 4：未核销退款规则
- specs/health-services-platform/tasks.md -> 阶段8-47/48/49

说明（v1）：
- 由于 v1 未引入真实支付退款通道，本实现将“同意退款”视为后端模拟成功：
  - 创建 Refund 记录（SUCCESS）
  - 更新 Order.payment_status=REFUNDED
  - 更新该订单下 Entitlement.status=REFUNDED
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.models.after_sale_case import AfterSaleCase
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType, AfterSaleDecision, AfterSaleStatus, AfterSaleType
from app.models.order import Order
from app.services.refund_service import execute_full_refund_for_order
from app.utils.db import get_session_factory
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.response import ok
from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.services.rbac import ActorContext
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["after-sales"])


def _require_user(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token)
    return payload



class AfterSaleCaseDTO(BaseModel):
    id: str
    orderId: str
    userId: str
    type: str
    status: str
    amount: float
    reason: str | None = None
    evidenceUrls: list[str] | None = None
    decidedBy: str | None = None
    decision: str | None = None
    decisionNotes: str | None = None
    createdAt: str
    updatedAt: str


def _dto(c: AfterSaleCase) -> dict:
    return AfterSaleCaseDTO(
        id=c.id,
        orderId=c.order_id,
        userId=c.user_id,
        type=c.type,
        status=c.status,
        amount=float(c.amount),
        reason=c.reason,
        evidenceUrls=c.evidence_urls,
        decidedBy=c.decided_by,
        decision=c.decision,
        decisionNotes=c.decision_notes,
        createdAt=c.created_at.astimezone().isoformat(),
        updatedAt=c.updated_at.astimezone().isoformat(),
    ).model_dump()


class CreateAfterSaleBody(BaseModel):
    orderId: str = Field(..., min_length=1)
    type: Literal["RETURN", "REFUND", "AFTER_SALE_SERVICE"] = Field(default=AfterSaleType.REFUND.value)
    reason: str | None = Field(default=None, max_length=512)
    evidenceUrls: list[str] | None = None


@router.post("/after-sales")
async def create_after_sale_case(
    request: Request,
    body: CreateAfterSaleBody,
    authorization: str | None = Header(default=None),
):
    payload = _require_user(authorization)
    user_id = str(payload["sub"])

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 订单必须存在且属于本人
        order = (
            await session.scalars(select(Order).where(Order.id == body.orderId, Order.user_id == user_id).limit(1))
        ).first()
        if order is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})

        # v1：仅已支付订单可发起售后（退款）
        if order.payment_status != "PAID":
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单状态不允许售后"})

        # v1：同一订单只允许存在 1 个未关闭售后单
        existing = (
            await session.scalars(
                select(AfterSaleCase)
                .where(
                    AfterSaleCase.order_id == order.id,
                    AfterSaleCase.user_id == user_id,
                    AfterSaleCase.status != AfterSaleStatus.CLOSED.value,
                )
                .limit(1)
            )
        ).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "售后申请已存在"})

        c = AfterSaleCase(
            id=str(uuid4()),
            order_id=order.id,
            user_id=user_id,
            type=str(body.type),
            status=AfterSaleStatus.SUBMITTED.value,
            amount=float(order.total_amount),
            reason=(body.reason.strip() if body.reason else None),
            evidence_urls=body.evidenceUrls,
            decided_by=None,
            decision=None,
            decision_notes=None,
        )
        session.add(c)
        await session.commit()

        # v1 最小：系统自动受理进入 UNDER_REVIEW（满足状态机 SUBMITTED -> UNDER_REVIEW）
        c.status = AfterSaleStatus.UNDER_REVIEW.value
        await session.commit()

    return ok(data=_dto(c), request_id=request.state.request_id)


@router.get("/admin/after-sales")
async def admin_list_after_sales(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    type: Literal["RETURN", "REFUND", "AFTER_SALE_SERVICE"] | None = None,
    status: Literal["SUBMITTED", "UNDER_REVIEW", "DECIDED", "CLOSED"] | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(AfterSaleCase)
    if type:
        stmt = stmt.where(AfterSaleCase.type == str(type))
    if status:
        stmt = stmt.where(AfterSaleCase.status == str(status))

    # 时间过滤：按 created_at
    def _parse_dt(raw: str) -> datetime:
        try:
            # 允许 YYYY-MM-DD 或 ISO8601（含时分秒/时区）
            if len(raw) == 10:
                return datetime.fromisoformat(raw + "T00:00:00")
            return datetime.fromisoformat(raw)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "时间参数不合法"}
            ) from exc

    if dateFrom:
        stmt = stmt.where(AfterSaleCase.created_at >= _parse_dt(str(dateFrom)))
    if dateTo:
        stmt = stmt.where(AfterSaleCase.created_at <= _parse_dt(str(dateTo)))

    stmt = stmt.order_by(AfterSaleCase.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        items = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_dto(x) for x in items], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


class AdminDecideAfterSaleBody(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    decisionNotes: str | None = Field(default=None, max_length=1024)


@router.put("/admin/after-sales/{id}/decide")
async def admin_decide_after_sale(
    request: Request,
    id: str,
    body: AdminDecideAfterSaleBody,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)

    session_factory = get_session_factory()
    async with session_factory() as session:
        c = (await session.scalars(select(AfterSaleCase).where(AfterSaleCase.id == id).limit(1))).first()
        if c is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "售后单不存在"})

        # 裁决写入
        try:
            decision = AfterSaleDecision(str(body.decision))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "decision 不合法"}
            ) from exc

        # 状态机幂等口径（你已拍板）
        # - 已 CLOSED 且 decision 相同：200 no-op（不重复退款/不重复写审计）
        # - 已 CLOSED 但 decision 不同：409 INVALID_STATE_TRANSITION
        # - 非 UNDER_REVIEW：409 INVALID_STATE_TRANSITION
        if c.status == AfterSaleStatus.CLOSED.value:
            if str(c.decision or "") == str(decision.value):
                return ok(data=_dto(c), request_id=request.state.request_id)
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "售后单状态不允许裁决"},
            )
        if c.status != AfterSaleStatus.UNDER_REVIEW.value:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "售后单状态不允许裁决"},
            )

        before_status = str(c.status)
        before_decision = str(c.decision or "")

        c.decided_by = admin_id
        c.decision = decision.value
        c.decision_notes = body.decisionNotes.strip() if body.decisionNotes else None
        c.status = AfterSaleStatus.DECIDED.value

        if decision == AfterSaleDecision.APPROVE:
            order = (await session.scalars(select(Order).where(Order.id == c.order_id).limit(1))).first()
            if order is None:
                raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})

            res = await execute_full_refund_for_order(session=session, order=order, reason=c.reason)
            if not res.ok:
                # v1：对外统一以 409 表示条件不满足或状态冲突
                raise HTTPException(
                    status_code=409,
                    detail={"code": res.error_code or "REFUND_NOT_ALLOWED", "message": "不满足退款条件"},
                )

        # v1 最小：裁决后即视为闭环（DECIDED -> CLOSED）
        c.status = AfterSaleStatus.CLOSED.value

        # 业务审计（必做）：action 统一 UPDATE；metadata 记录 decision + before/after
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="AFTER_SALES",
                resource_id=str(c.id),
                summary=f"ADMIN 售后裁决（{decision.value}）",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "afterSaleId": str(c.id),
                    "orderId": str(c.order_id),
                    "userId": str(c.user_id),
                    "decision": str(decision.value),
                    "beforeStatus": before_status,
                    "afterStatus": str(c.status),
                    "beforeDecision": before_decision,
                    "afterDecision": str(c.decision or ""),
                },
            )
        )

        await session.commit()

    return ok(data=_dto(c), request_id=request.state.request_id)
