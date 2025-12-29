"""Admin 安全相关（v1）。

规格来源：
- specs/health-services-platform/tasks.md -> REQ-ADMIN-P1-001
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.api.v1.deps import require_admin
from app.models.admin import Admin
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["admin-security"])


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


@router.get("/admin/auth/security")
async def admin_get_security(request: Request, _admin: ActorContext = Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        a = (await session.scalars(select(Admin).where(Admin.id == str(_admin.sub)).limit(1))).first()

    if a is None or a.status != "ACTIVE":
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})

    phone = str(a.phone or "").strip()
    enabled = bool(phone)
    return ok(
        data={"twoFaEnabled": enabled, "phoneMasked": _mask_phone(phone) if enabled else None},
        request_id=request.state.request_id,
    )


