"""Admin 用户与身份查询接口（v1 最小可执行）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-007
- specs/health-services-platform/prototypes/admin.md -> 用户列表
- specs/health-services-platform/design.md -> User 模型（identities/enterprise）

接口（v1 最小）：
- GET /api/v1/admin/users
- GET /api/v1/admin/users/{id}

说明：
- v1 默认返回手机号脱敏字段 phoneMasked，避免在列表接口泄露明文。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.v1.deps import require_admin
from app.models.enums import UserIdentity
from app.models.user import User
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-users"])


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


def _user_list_item(u: User) -> dict:
    return {
        "id": u.id,
        "phoneMasked": _mask_phone(u.phone),
        "nickname": u.nickname,
        "identities": u.identities or [],
        "enterpriseId": u.enterprise_id,
        "enterpriseName": u.enterprise_name,
        "createdAt": _iso(u.created_at),
    }


def _user_detail(u: User) -> dict:
    return {
        "id": u.id,
        "phoneMasked": _mask_phone(u.phone),
        "nickname": u.nickname,
        "avatar": u.avatar,
        "identities": u.identities or [],
        "enterpriseId": u.enterprise_id,
        "enterpriseName": u.enterprise_name,
        "bindingTime": _iso(u.binding_time),
        "createdAt": _iso(u.created_at),
        "updatedAt": _iso(u.updated_at),
    }


@router.get("/admin/users")
async def admin_list_users(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    phone: str | None = None,
    nickname: str | None = None,
    identity: str | None = None,
    enterpriseId: str | None = None,
    enterpriseName: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(User)

    if phone and phone.strip():
        stmt = stmt.where(User.phone.like(f"%{phone.strip()}%"))

    if nickname and nickname.strip():
        stmt = stmt.where(User.nickname.like(f"%{nickname.strip()}%"))

    if enterpriseId and enterpriseId.strip():
        stmt = stmt.where(User.enterprise_id == enterpriseId.strip())

    if enterpriseName and enterpriseName.strip():
        stmt = stmt.where(User.enterprise_name.like(f"%{enterpriseName.strip()}%"))

    if identity and identity.strip():
        ident = identity.strip()
        if ident not in {UserIdentity.MEMBER.value, UserIdentity.EMPLOYEE.value}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "identity 不合法"})
        # MySQL JSON：使用 JSON_CONTAINS
        stmt = stmt.where(User.identities.contains([ident]))

    stmt = stmt.order_by(User.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_user_list_item(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.get("/admin/users/{id}")
async def admin_get_user(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin),
):
    _ = _admin

    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(User).where(User.id == id).limit(1))).first()

    if u is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "用户不存在"})

    return ok(data=_user_detail(u), request_id=request.state.request_id)
