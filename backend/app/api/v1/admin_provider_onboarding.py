"""Admin：Provider 健行天下开通审核（v1）。

规格来源：
- specs/health-services-platform/provider-onboarding-v1.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.v1.deps import require_admin
from app.models.enums import ProviderHealthCardStatus
from app.models.provider import Provider
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso


router = APIRouter(tags=["admin-provider-onboarding"])

def _dto(p: Provider) -> dict:
    return {
        "providerId": p.id,
        "providerName": p.name,
        "infraCommerceStatus": p.infra_commerce_status,
        "healthCardStatus": p.health_card_status,
        "agreementAcceptedAt": _iso(p.health_card_agreement_accepted_at),
        "submittedAt": _iso(p.health_card_submitted_at),
        "reviewedAt": _iso(p.health_card_reviewed_at),
        "notes": p.health_card_review_notes,
        "updatedAt": _iso(p.updated_at),
    }


@router.get("/admin/provider-onboarding/health-card")
async def admin_list_provider_health_card_onboarding(
    request: Request,
    page: int = 1,
    pageSize: int = 20,
    status: Literal["NOT_APPLIED", "SUBMITTED", "APPROVED", "REJECTED"] | None = None,
    keyword: str | None = None,
    _admin=Depends(require_admin),
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))
    stmt = select(Provider)
    if status:
        stmt = stmt.where(Provider.health_card_status == status)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where((Provider.id.like(kw)) | (Provider.name.like(kw)))

    stmt = stmt.order_by(Provider.updated_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(data={"items": [_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


class DecideBody(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    notes: str | None = Field(default=None, max_length=512)


@router.put("/admin/provider-onboarding/{providerId}/health-card/decide")
async def admin_decide_provider_health_card_onboarding(
    request: Request,
    providerId: str,
    body: DecideBody,
    _admin=Depends(require_admin),
):
    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (await session.scalars(select(Provider).where(Provider.id == providerId).limit(1))).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "provider 不存在"})
        if p.health_card_status != ProviderHealthCardStatus.SUBMITTED.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "仅允许审核 SUBMITTED 状态"})

        now = datetime.now(tz=UTC).replace(tzinfo=None)
        if body.decision == "APPROVE":
            p.health_card_status = ProviderHealthCardStatus.APPROVED.value
            p.health_card_review_notes = (body.notes.strip() if body.notes and body.notes.strip() else None)
        else:
            p.health_card_status = ProviderHealthCardStatus.REJECTED.value
            p.health_card_review_notes = (body.notes.strip() if body.notes and body.notes.strip() else "未通过")

        p.health_card_reviewed_at = now
        p.updated_at = now
        await session.commit()
        await session.refresh(p)

    return ok(data=_dto(p), request_id=request.state.request_id)

