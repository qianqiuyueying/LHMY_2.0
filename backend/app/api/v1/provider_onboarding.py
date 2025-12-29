"""Provider 开通流程（基建联防/健行天下）v1。

规格来源：
- specs/health-services-platform/provider-onboarding-v1.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.models.admin import Admin
from app.models.enums import NotificationReceiverType, NotificationStatus, ProviderHealthCardStatus, ProviderInfraCommerceStatus
from app.models.notification import Notification
from app.models.provider import Provider
from app.models.venue import Venue
from app.services.provider_auth_context import require_provider_context
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso


router = APIRouter(tags=["provider-onboarding"])

async def _assert_min_venue_info(*, session, provider_id: str) -> None:
    """v1 最小：至少有 1 个场所且 name/address 非空。"""

    rows = (await session.scalars(select(Venue).where(Venue.provider_id == provider_id).limit(10))).all()
    if not rows:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "请先创建并完善场所信息"})
    for v in rows:
        if str(v.name or "").strip() and str(v.address or "").strip():
            return
    raise HTTPException(
        status_code=400,
        detail={"code": "INVALID_ARGUMENT", "message": "请先完善场所信息：场所名称与地址不能为空"},
    )


def _dto(p: Provider) -> dict:
    return {
        "infraCommerceStatus": p.infra_commerce_status,
        "healthCardStatus": p.health_card_status,
        "infraAgreementAcceptedAt": _iso(getattr(p, "infra_commerce_agreement_accepted_at", None)),
        "agreementAcceptedAt": _iso(p.health_card_agreement_accepted_at),
        "updatedAt": _iso(p.updated_at),
        "submittedAt": _iso(p.health_card_submitted_at),
        "reviewedAt": _iso(p.health_card_reviewed_at),
        "notes": p.health_card_review_notes,
    }


@router.get("/provider/onboarding")
async def provider_get_onboarding(request: Request, authorization: str | None = Header(default=None)):
    ctx = await require_provider_context(authorization=authorization)
    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (await session.scalars(select(Provider).where(Provider.id == ctx.providerId).limit(1))).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "provider 不存在"})
    return ok(data=_dto(p), request_id=request.state.request_id)


class OpenInfraBody(BaseModel):
    agree: bool


@router.post("/provider/onboarding/infra/open")
async def provider_open_infra(request: Request, body: OpenInfraBody, authorization: str | None = Header(default=None)):
    ctx = await require_provider_context(authorization=authorization)
    if body.agree is not True:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "必须勾选并同意协议"})
    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (await session.scalars(select(Provider).where(Provider.id == ctx.providerId).limit(1))).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "provider 不存在"})

        await _assert_min_venue_info(session=session, provider_id=p.id)

        now = datetime.now(tz=UTC).replace(tzinfo=None)
        p.infra_commerce_status = ProviderInfraCommerceStatus.OPENED.value
        p.infra_commerce_agreement_accepted_at = now
        p.updated_at = now
        await session.commit()
        await session.refresh(p)
    return ok(data=_dto(p), request_id=request.state.request_id)


class SubmitHealthCardBody(BaseModel):
    agree: bool


@router.post("/provider/onboarding/health-card/submit")
async def provider_submit_health_card(request: Request, body: SubmitHealthCardBody, authorization: str | None = Header(default=None)):
    ctx = await require_provider_context(authorization=authorization)
    if body.agree is not True:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "必须勾选并同意协议"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (await session.scalars(select(Provider).where(Provider.id == ctx.providerId).limit(1))).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "provider 不存在"})

        await _assert_min_venue_info(session=session, provider_id=p.id)

        # v1：允许 NOT_APPLIED/REJECTED 重新提交；SUBMITTED/APPROVED 不重复提交
        if p.health_card_status in {ProviderHealthCardStatus.SUBMITTED.value, ProviderHealthCardStatus.APPROVED.value}:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "当前状态不允许重复提交"})

        now = datetime.now(tz=UTC).replace(tzinfo=None)
        p.health_card_status = ProviderHealthCardStatus.SUBMITTED.value
        p.health_card_agreement_accepted_at = now
        p.health_card_submitted_at = now
        p.health_card_reviewed_at = None
        p.health_card_review_notes = None
        p.updated_at = now

        # v1：系统站内通知（Admin 顶栏）——提醒运营有新的开通申请需要审核
        # 说明：Notification 模型为“站内通知记录”，并不等同于短信/推送；仅用于后台顶栏可见与可标记已读。
        admins = (await session.scalars(select(Admin).where(Admin.status == "ACTIVE"))).all()
        for a in admins:
            session.add(
                Notification(
                    id=str(uuid4()),
                    receiver_type=NotificationReceiverType.ADMIN.value,
                    receiver_id=a.id,
                    title="新的健行天下开通申请待审核",
                    content=f"Provider 已提交健行天下开通申请：{p.name}（{p.id}）。请前往“供给侧 → 健行天下开通审核”处理。",
                    status=NotificationStatus.UNREAD.value,
                    created_at=now,
                    read_at=None,
                )
            )

        await session.commit()
        await session.refresh(p)
    return ok(data=_dto(p), request_id=request.state.request_id)

