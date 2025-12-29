"""Admin：经销商分账与结算（v1 最小可上线）。

规格来源：
- specs/health-services-platform/dealer-settlement-v1.md
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.dealer import Dealer
from app.models.dealer_settlement_account import DealerSettlementAccount
from app.models.enums import AuditAction, AuditActorType, DealerStatus, OrderType, PaymentStatus, SettlementStatus
from app.models.order import Order
from app.models.settlement_record import SettlementRecord
from app.models.system_config import SystemConfig
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso


router = APIRouter(tags=["admin-dealer-settlements"])

_KEY_COMMISSION = "DEALER_COMMISSION_RULES"
_CYCLE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _parse_cycle_to_range(cycle: str) -> tuple[datetime, datetime]:
    """YYYY-MM -> [start, end)（UTC 口径，存储为 naive datetime）"""

    s = str(cycle or "").strip()
    if not _CYCLE_RE.fullmatch(s):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "cycle 格式不合法，应为 YYYY-MM"})
    y = int(s[:4])
    m = int(s[5:7])
    start = datetime(y, m, 1, tzinfo=UTC).replace(tzinfo=None)
    if m == 12:
        end = datetime(y + 1, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    else:
        end = datetime(y, m + 1, 1, tzinfo=UTC).replace(tzinfo=None)
    return start, end


def _mask_account_no(account_no: str | None) -> str | None:
    if not account_no:
        return None
    s = str(account_no).strip()
    if len(s) <= 8:
        return None
    return f"{s[:4]}****{s[-4:]}"


def _mask_reference_last4(ref: str | None) -> str | None:
    """资金类字段避免入审计明文：仅保留后 4 位（不足则不记）。"""

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
    }
    # contactPhone 属于 PII，结算类场景一律脱敏
    if isinstance(contact_phone, str):
        s = contact_phone.strip()
        if len(s) >= 7:
            out["contactPhoneMasked"] = f"{s[:3]}****{s[-4:]}"
    return out


async def _get_or_create_cfg(session) -> SystemConfig:
    cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_COMMISSION).limit(1))).first()
    if cfg is not None:
        return cfg
    cfg = SystemConfig(
        id=str(uuid4()),
        key=_KEY_COMMISSION,
        value_json={"defaultRate": 0.1, "dealerOverrides": {}, "updatedAt": datetime.now(tz=UTC).isoformat()},
        description="Dealer commission rules (v1)",
        status="ENABLED",
    )
    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)
    return cfg


def _normalize_rate(v) -> float:
    try:
        x = float(v)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "分账比例必须是数字"}) from exc
    if x < 0 or x > 1:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "分账比例必须在 0~1 之间"})
    return float(x)


class PutCommissionBody(BaseModel):
    defaultRate: float = Field(..., ge=0, le=1)
    dealerOverrides: dict[str, float] | None = None

    @model_validator(mode="after")
    def _norm(self):
        self.defaultRate = _normalize_rate(self.defaultRate)
        if self.dealerOverrides is None:
            self.dealerOverrides = {}
        # 过滤空 key + 归一化 value
        out: dict[str, float] = {}
        for k, v in (self.dealerOverrides or {}).items():
            kk = str(k or "").strip()
            if not kk:
                continue
            out[kk] = _normalize_rate(v)
        self.dealerOverrides = out
        return self


@router.get("/admin/dealer-commission")
async def admin_get_dealer_commission(request: Request, _admin=Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (await session.scalars(select(SystemConfig).where(SystemConfig.key == _KEY_COMMISSION).limit(1))).first()
    if cfg is None:
        return ok(data={"defaultRate": 0.1, "dealerOverrides": {}, "updatedAt": None}, request_id=request.state.request_id)
    raw = cfg.value_json or {}
    return ok(
        data={
            "defaultRate": float(raw.get("defaultRate") or 0),
            "dealerOverrides": raw.get("dealerOverrides") or {},
            "updatedAt": raw.get("updatedAt"),
        },
        request_id=request.state.request_id,
    )


@router.put("/admin/dealer-commission")
async def admin_put_dealer_commission(request: Request, body: PutCommissionBody, admin=Depends(require_admin)):
    now = datetime.now(tz=UTC).isoformat()
    value = {"defaultRate": body.defaultRate, "dealerOverrides": body.dealerOverrides or {}, "updatedAt": now}

    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = await _get_or_create_cfg(session)
        cfg.value_json = value
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(getattr(admin, "sub", "") or ""),
                action=AuditAction.UPDATE.value,
                resource_type="SYSTEM_CONFIG",
                resource_id=_KEY_COMMISSION,
                summary="更新经销商分账规则",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "key": _KEY_COMMISSION,
                    "defaultRate": body.defaultRate,
                    "dealerOverridesCount": int(len(body.dealerOverrides or {})),
                },
            )
        )
        await session.commit()
        await session.refresh(cfg)

    return ok(data=value, request_id=request.state.request_id)


class GenerateBody(BaseModel):
    cycle: str


@router.post("/admin/dealer-settlements/generate")
async def admin_generate_dealer_settlements(request: Request, body: GenerateBody, admin=Depends(require_admin_phone_bound)):
    cycle = str(body.cycle or "").strip()
    start, end = _parse_cycle_to_range(cycle)

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 读分账规则
        cfg = await _get_or_create_cfg(session)
        raw = cfg.value_json or {}
        default_rate = _normalize_rate(raw.get("defaultRate") or 0.0)
        overrides = raw.get("dealerOverrides") or {}
        if not isinstance(overrides, dict):
            overrides = {}

        # 聚合当月已支付的健行天下订单（按 paid_at 落在周期）
        agg = (
            await session.execute(
                select(
                    Order.dealer_id,
                    func.count().label("order_count"),
                    func.sum(Order.total_amount).label("gross_amount"),
                )
                .where(
                    Order.order_type == OrderType.SERVICE_PACKAGE.value,
                    Order.payment_status == PaymentStatus.PAID.value,
                    Order.paid_at.is_not(None),
                    Order.paid_at >= start,
                    Order.paid_at < end,
                    Order.dealer_id.is_not(None),
                )
                .group_by(Order.dealer_id)
            )
        ).all()

        dealer_ids = [str(x[0]) for x in agg if x[0]]
        if dealer_ids:
            dealers = (await session.scalars(select(Dealer).where(Dealer.id.in_(dealer_ids)))).all()
        else:
            dealers = []
        dealer_map = {d.id: d for d in dealers}

        created = 0
        updated_or_existing = 0
        items: list[dict] = []

        for dealer_id, order_count, gross_amount in agg:
            did = str(dealer_id)
            d = dealer_map.get(did)
            # v1 最小：仅对 ACTIVE dealer 出账
            if d is None or d.status != DealerStatus.ACTIVE.value:
                continue

            rate = default_rate
            try:
                if did in overrides:
                    rate = _normalize_rate(overrides.get(did))
            except HTTPException:
                rate = default_rate

            gross = float(gross_amount or 0.0)
            amount = float(round(gross * rate, 2))
            oc = int(order_count or 0)

            # 读取经销商结算账户（可为空）；保存到结算单快照，避免后续账户改动影响对账
            acct = (
                await session.scalars(select(DealerSettlementAccount).where(DealerSettlementAccount.dealer_id == did).limit(1))
            ).first()
            payout_method = acct.method if acct is not None else None
            payout_account_json = None
            if acct is not None:
                payout_account_json = {
                    "method": acct.method,
                    "accountName": acct.account_name,
                    "accountNoMasked": _mask_account_no(acct.account_no),
                    "bankName": acct.bank_name,
                    "bankBranch": acct.bank_branch,
                    "contactPhone": acct.contact_phone,
                }

            existing = (
                await session.scalars(
                    select(SettlementRecord).where(SettlementRecord.dealer_id == did, SettlementRecord.cycle == cycle).limit(1)
                )
            ).first()
            if existing is not None:
                # 幂等：已存在则返回现有，不覆盖（避免重复生成引发对账口径漂移）
                updated_or_existing += 1
                items.append(
                    {
                        "id": existing.id,
                        "dealerId": existing.dealer_id,
                        "cycle": existing.cycle,
                        "orderCount": int(existing.order_count),
                        "amount": float(existing.amount),
                        "status": existing.status,
                        "createdAt": _iso(existing.created_at),
                        "settledAt": _iso(existing.settled_at),
                        "grossAmount": gross,
                        "commissionRate": rate,
                        "generated": False,
                    }
                )
                continue

            row = SettlementRecord(
                id=str(uuid4()),
                dealer_id=did,
                cycle=cycle,
                order_count=oc,
                amount=amount,
                status=SettlementStatus.PENDING_CONFIRM.value,
                payout_method=payout_method,
                payout_account_json=payout_account_json,
                payout_reference=None,
                payout_note=None,
                payout_marked_by=None,
                payout_marked_at=None,
                created_at=datetime.now(tz=UTC).replace(tzinfo=None),
                settled_at=None,
            )
            session.add(row)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                # 并发/重复：按幂等视为已存在
                existing2 = (
                    await session.scalars(
                        select(SettlementRecord)
                        .where(SettlementRecord.dealer_id == did, SettlementRecord.cycle == cycle)
                        .limit(1)
                    )
                ).first()
                if existing2 is not None:
                    updated_or_existing += 1
                    items.append(
                        {
                            "id": existing2.id,
                            "dealerId": existing2.dealer_id,
                            "cycle": existing2.cycle,
                            "orderCount": int(existing2.order_count),
                            "amount": float(existing2.amount),
                            "status": existing2.status,
                            "createdAt": _iso(existing2.created_at),
                            "settledAt": _iso(existing2.settled_at),
                            "grossAmount": gross,
                            "commissionRate": rate,
                            "generated": False,
                        }
                    )
                    continue
                raise
            await session.refresh(row)
            created += 1
            items.append(
                {
                    "id": row.id,
                    "dealerId": row.dealer_id,
                    "cycle": row.cycle,
                    "orderCount": int(row.order_count),
                    "amount": float(row.amount),
                    "status": row.status,
                    "createdAt": _iso(row.created_at),
                    "settledAt": _iso(row.settled_at),
                    "payoutMethod": row.payout_method,
                    "payoutAccount": row.payout_account_json,
                    "payoutReference": row.payout_reference,
                    "payoutNote": row.payout_note,
                    "payoutMarkedAt": _iso(row.payout_marked_at),
                    "grossAmount": gross,
                    "commissionRate": rate,
                    "generated": True,
                }
            )

        # 审计：结算批次生成（资金高风险；避免记录账户明细/敏感信息）
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(getattr(admin, "sub", "") or ""),
                action=AuditAction.CREATE.value,
                resource_type="DEALER_SETTLEMENT_BATCH",
                resource_id=cycle,
                summary=f"生成经销商结算批次：{cycle}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "cycle": cycle,
                    "created": int(created),
                    "existing": int(updated_or_existing),
                },
            )
        )
        await session.commit()

    return ok(
        data={"cycle": cycle, "created": created, "existing": updated_or_existing, "items": items},
        request_id=request.state.request_id,
    )


@router.get("/admin/dealer-settlements")
async def admin_list_dealer_settlements(
    request: Request,
    page: int = 1,
    pageSize: int = 20,
    dealerId: str | None = None,
    cycle: str | None = None,
    status: str | None = None,
    _admin=Depends(require_admin),
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))
    stmt = select(SettlementRecord)
    if dealerId and dealerId.strip():
        stmt = stmt.where(SettlementRecord.dealer_id == dealerId.strip())
    if cycle and cycle.strip():
        stmt = stmt.where(SettlementRecord.cycle == cycle.strip())
    if status and status.strip():
        stmt = stmt.where(SettlementRecord.status == status.strip())
    stmt = stmt.order_by(SettlementRecord.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items = []
    for x in rows:
        items.append(
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
        )
    return ok(data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


class MarkSettledBody(BaseModel):
    payoutReference: str | None = Field(default=None, max_length=128)
    payoutNote: str | None = Field(default=None, max_length=512)


@router.post("/admin/dealer-settlements/{id}/mark-settled")
async def admin_mark_dealer_settlement_settled(
    request: Request,
    id: str,
    body: MarkSettledBody,
    admin=Depends(require_admin_phone_bound),
):
    settlement_id = str(id or "").strip()
    if not settlement_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "id 不能为空"})

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(SettlementRecord).where(SettlementRecord.id == settlement_id).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "结算单不存在"})
        if row.status == SettlementStatus.FROZEN.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "结算单已冻结，禁止结算"})

        # 幂等：已是目标态（SETTLED）则 no-op，返回当前状态（不得覆盖已写入的打款信息）
        if row.status == SettlementStatus.SETTLED.value:
            return ok(
                data={
                    "id": row.id,
                    "status": row.status,
                    "settledAt": _iso(row.settled_at),
                    "payoutReferenceLast4": _mask_reference_last4(row.payout_reference),
                    "payoutNote": row.payout_note,
                    "payoutMarkedAt": _iso(row.payout_marked_at),
                },
                request_id=request.state.request_id,
            )

        # 非法状态流转兜底（理论上 v1 只有 PENDING_CONFIRM/FROZEN/SETTLED）
        if row.status != SettlementStatus.PENDING_CONFIRM.value:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "结算单状态已变化，请刷新后重试"},
            )

        before_status = row.status
        row.status = SettlementStatus.SETTLED.value
        row.settled_at = now
        row.payout_reference = (body.payoutReference or "").strip() or None
        row.payout_note = (body.payoutNote or "").strip() or None
        row.payout_marked_by = str(getattr(admin, "sub", "") or "")
        row.payout_marked_at = now

        # 审计：资金高风险（不记录敏感明文：仅保留 payoutReference 后 4 位，note 仅记是否存在）
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(getattr(admin, "sub", "") or ""),
                action=AuditAction.UPDATE.value,
                resource_type="DEALER_SETTLEMENT",
                resource_id=row.id,
                summary=f"标记结算单已结算：{row.id}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "beforeStatus": before_status,
                    "afterStatus": SettlementStatus.SETTLED.value,
                    "cycle": row.cycle,
                    "dealerId": row.dealer_id,
                    "amount": float(row.amount),
                    "payoutReferenceLast4": _mask_reference_last4(row.payout_reference),
                    "hasPayoutNote": bool(row.payout_note),
                },
            )
        )
        await session.commit()
        await session.refresh(row)

    return ok(
        data={
            "id": row.id,
            "status": row.status,
            "settledAt": _iso(row.settled_at),
            "payoutReferenceLast4": _mask_reference_last4(row.payout_reference),
            "payoutNote": row.payout_note,
            "payoutMarkedAt": _iso(row.payout_marked_at),
        },
        request_id=request.state.request_id,
    )

