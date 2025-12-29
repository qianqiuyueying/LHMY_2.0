"""协议/条款读侧（v1 最小）。

规格来源：
- specs/health-services-platform/tasks.md -> REQ-ADMIN-P0-008
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.models.enums import LegalAgreementStatus
from app.models.legal_agreement import LegalAgreement
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["legal"])


@router.get("/legal/{code}")
async def get_legal_agreement(request: Request, code: str):
    code = str(code or "").strip()
    if not code:
        return ok(data={"code": "", "title": "", "contentHtml": "", "version": "0"}, request_id=request.state.request_id)

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (
            await session.scalars(
                select(LegalAgreement).where(
                    LegalAgreement.code == code, LegalAgreement.status == LegalAgreementStatus.PUBLISHED.value
                )
            )
        ).first()

    if row is None:
        return ok(data={"code": code, "title": "", "contentHtml": "", "version": "0"}, request_id=request.state.request_id)

    return ok(
        data={"code": row.code, "title": row.title, "contentHtml": row.content_html, "version": row.version},
        request_id=request.state.request_id,
    )


