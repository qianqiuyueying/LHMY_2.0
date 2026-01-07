"""Admin 账号管理（管理员创建/重置 Provider/Dealer 后台账号）。

规格来源：
- specs/功能实现/admin/tasks.md -> T-A04/T-A05/T-A06

约束（v1）：
- 仅 ADMIN 可访问
- 仅支持 ProviderUser（actorType=PROVIDER）与 DealerUser（actorType=DEALER）
- 创建时按“方案A”同时创建主体（Provider/Dealer）
- 密码仅在创建/重置的响应中返回一次，不提供明文查询接口
"""

from __future__ import annotations

import secrets
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.dealer import Dealer
from app.models.dealer_user import DealerUser
from app.models.enums import AuditAction, AuditActorType
from app.models.provider import Provider
from app.models.provider_staff import ProviderStaff
from app.models.provider_user import ProviderUser
from app.models.venue import Venue
from app.services.password_hashing import hash_password
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-accounts"])

def _gen_password(length: int = 12) -> str:
    # 约束：可复制、可输入；避免易混淆字符
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(max(8, int(length))))


class AdminCreateProviderUserBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    providerName: str = Field(..., min_length=1, max_length=256)


class AdminCreateDealerUserBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    dealerName: str = Field(..., min_length=1, max_length=256)


class AdminCreateProviderStaffBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    providerId: str = Field(..., min_length=1, max_length=36)


class AdminCreateAdminUserBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)


@router.get("/admin/admin-users")
async def admin_list_admin_users(
    request: Request,
    _admin=Depends(require_admin),
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Admin)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(Admin.username.like(kw))

    stmt = stmt.order_by(Admin.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items = []
    for u in rows:
        items.append(
            {
                "id": u.id,
                "username": u.username,
                "status": u.status,
                "phone": u.phone,
                "createdAt": _iso(u.created_at),
                "updatedAt": _iso(u.updated_at),
            }
        )
    return ok(data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


@router.post("/admin/admin-users")
async def admin_create_admin_user(
    request: Request,
    body: AdminCreateAdminUserBody,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "username 不能为空"})

    password = _gen_password()
    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = (await session.scalars(select(Admin).where(Admin.username == username).limit(1))).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "username 已存在"})

        user_id = str(uuid4())
        session.add(
            Admin(
                id=user_id,
                username=username,
                password_hash=hash_password(password=password),
                status="ACTIVE",
                phone=None,
            )
        )
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.CREATE.value,
                resource_type="ADMIN_USER",
                resource_id=user_id,
                summary=f"ADMIN 创建 Admin 账号：{username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": user_id,
                    "username": username,
                    "passwordReturnedOnce": True,
                },
            )
        )
        await session.commit()

    return ok(
        data={"adminUser": {"id": user_id, "username": username, "status": "ACTIVE", "phone": None}, "password": password},
        request_id=request.state.request_id,
    )


@router.post("/admin/admin-users/{id}/reset-password")
async def admin_reset_admin_user_password(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    password = _gen_password()
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(Admin).where(Admin.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() != "ACTIVE":
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "账号未启用，不能重置密码"})
        u.password_hash = hash_password(password=password)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="ADMIN_USER",
                resource_id=u.id,
                summary=f"ADMIN 重置 Admin 账号密码：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "username": u.username,
                    "passwordReturnedOnce": True,
                },
            )
        )
        await session.commit()
    return ok(
        data={"adminUser": {"id": u.id, "username": u.username, "status": u.status, "phone": u.phone}, "password": password},
        request_id=request.state.request_id,
    )


@router.post("/admin/admin-users/{id}/suspend")
async def admin_suspend_admin_user(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(Admin).where(Admin.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() != "SUSPENDED":
            before = u.status
            u.status = "SUSPENDED"
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.ADMIN.value,
                    actor_id=admin_id,
                    action=AuditAction.UPDATE.value,
                    resource_type="ADMIN_USER",
                    resource_id=u.id,
                    summary=f"ADMIN 冻结 Admin 账号：{u.username}",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={
                        "path": request.url.path,
                        "method": request.method,
                        "requestId": request.state.request_id,
                        "targetUserId": u.id,
                        "username": u.username,
                        "beforeStatus": before,
                        "afterStatus": u.status,
                    },
                )
            )
            await session.commit()
    return ok(data={"adminUser": {"id": u.id, "username": u.username, "status": u.status, "phone": u.phone}}, request_id=request.state.request_id)


@router.post("/admin/admin-users/{id}/activate")
async def admin_activate_admin_user(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(Admin).where(Admin.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() != "ACTIVE":
            before = u.status
            u.status = "ACTIVE"
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.ADMIN.value,
                    actor_id=admin_id,
                    action=AuditAction.UPDATE.value,
                    resource_type="ADMIN_USER",
                    resource_id=u.id,
                    summary=f"ADMIN 启用 Admin 账号：{u.username}",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={
                        "path": request.url.path,
                        "method": request.method,
                        "requestId": request.state.request_id,
                        "targetUserId": u.id,
                        "username": u.username,
                        "beforeStatus": before,
                        "afterStatus": u.status,
                    },
                )
            )
            await session.commit()
    return ok(data={"adminUser": {"id": u.id, "username": u.username, "status": u.status, "phone": u.phone}}, request_id=request.state.request_id)


@router.get("/admin/provider-users")
async def admin_list_provider_users(
    request: Request,
    _admin=Depends(require_admin),
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(ProviderUser, Provider.name).join(Provider, Provider.id == ProviderUser.provider_id, isouter=True)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(ProviderUser.username.like(kw) | Provider.name.like(kw))

    stmt = stmt.order_by(ProviderUser.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items = []
    for u, provider_name in rows:
        items.append(
            {
                "id": u.id,
                "username": u.username,
                "providerId": u.provider_id,
                "providerName": provider_name or "",
                "status": u.status,
                "createdAt": _iso(u.created_at),
                "updatedAt": _iso(u.updated_at),
            }
        )
    return ok(data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


@router.post("/admin/provider-users")
async def admin_create_provider_user(
    request: Request,
    body: AdminCreateProviderUserBody,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    username = body.username.strip()
    provider_name = body.providerName.strip()
    if not username:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "username 不能为空"})
    if not provider_name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "providerName 不能为空"})

    password = _gen_password()

    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = (await session.scalars(select(ProviderUser).where(ProviderUser.username == username).limit(1))).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "username 已存在"})

        provider_id = str(uuid4())
        user_id = str(uuid4())
        session.add(Provider(id=provider_id, name=provider_name))
        # v1 最小可执行：同步创建一个“默认场所”，用于 provider 侧完成“场所信息维护”闭环
        # 注意：名称不再追加“（默认场所）”后缀；该后缀会污染对外展示（官网/小程序）与影响用户感知。
        session.add(
            Venue(
                id=str(uuid4()),
                provider_id=provider_id,
                name=provider_name,
            )
        )
        session.add(
            ProviderUser(
                id=user_id,
                provider_id=provider_id,
                username=username,
                password_hash=hash_password(password=password),
                status="ACTIVE",
            )
        )
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.CREATE.value,
                resource_type="PROVIDER_USER",
                resource_id=user_id,
                summary=f"ADMIN 创建 Provider 账号：{username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": user_id,
                    "providerId": provider_id,
                    "providerName": provider_name,
                    "username": username,
                    "passwordReturnedOnce": True,
                },
            )
        )
        await session.commit()

    return ok(
        data={
            "providerUser": {
                "id": user_id,
                "username": username,
                "providerId": provider_id,
                "providerName": provider_name,
                "status": "ACTIVE",
            },
            "password": password,
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/provider-users/{id}/reset-password")
async def admin_reset_provider_user_password(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    password = _gen_password()
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(ProviderUser).where(ProviderUser.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() != "ACTIVE":
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "账号未启用，不能重置密码"})
        u.password_hash = hash_password(password=password)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="PROVIDER_USER",
                resource_id=u.id,
                summary=f"ADMIN 重置 Provider 账号密码：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "providerId": u.provider_id,
                    "username": u.username,
                    "passwordReturnedOnce": True,
                },
            )
        )
        await session.commit()

        provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
        provider_name = provider.name if provider is not None else ""

    return ok(
        data={
            "providerUser": {
                "id": u.id,
                "username": u.username,
                "providerId": u.provider_id,
                "providerName": provider_name,
                "status": u.status,
            },
            "password": password,
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/provider-users/{id}/suspend")
async def admin_suspend_provider_user(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    """冻结 ProviderUser（v1 最小）：仅切换状态，不影响历史数据。冻结后禁止登录与发起新业务。"""
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(ProviderUser).where(ProviderUser.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() == "SUSPENDED":
            provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
            provider_name = provider.name if provider is not None else ""
            return ok(
                data={
                    "providerUser": {
                        "id": u.id,
                        "username": u.username,
                        "providerId": u.provider_id,
                        "providerName": provider_name,
                        "status": u.status,
                    }
                },
                request_id=request.state.request_id,
            )
        before = u.status
        u.status = "SUSPENDED"
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="PROVIDER_USER",
                resource_id=u.id,
                summary=f"ADMIN 冻结 Provider 账号：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "providerId": u.provider_id,
                    "username": u.username,
                    "beforeStatus": before,
                    "afterStatus": u.status,
                },
            )
        )
        await session.commit()
        provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
        provider_name = provider.name if provider is not None else ""
    return ok(
        data={
            "providerUser": {
                "id": u.id,
                "username": u.username,
                "providerId": u.provider_id,
                "providerName": provider_name,
                "status": u.status,
            }
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/provider-users/{id}/activate")
async def admin_activate_provider_user(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    """启用 ProviderUser（v1 最小）：仅切换状态。"""
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(ProviderUser).where(ProviderUser.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() == "ACTIVE":
            provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
            provider_name = provider.name if provider is not None else ""
            return ok(
                data={
                    "providerUser": {
                        "id": u.id,
                        "username": u.username,
                        "providerId": u.provider_id,
                        "providerName": provider_name,
                        "status": u.status,
                    }
                },
                request_id=request.state.request_id,
            )
        before = u.status
        u.status = "ACTIVE"
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="PROVIDER_USER",
                resource_id=u.id,
                summary=f"ADMIN 启用 Provider 账号：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "providerId": u.provider_id,
                    "username": u.username,
                    "beforeStatus": before,
                    "afterStatus": u.status,
                },
            )
        )
        await session.commit()
        provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
        provider_name = provider.name if provider is not None else ""
    return ok(
        data={
            "providerUser": {
                "id": u.id,
                "username": u.username,
                "providerId": u.provider_id,
                "providerName": provider_name,
                "status": u.status,
            }
        },
        request_id=request.state.request_id,
    )


@router.get("/admin/provider-staff")
async def admin_list_provider_staff(
    request: Request,
    _admin=Depends(require_admin),
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(ProviderStaff, Provider.name).join(Provider, Provider.id == ProviderStaff.provider_id, isouter=True)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(ProviderStaff.username.like(kw) | Provider.name.like(kw) | ProviderStaff.provider_id.like(kw))

    stmt = stmt.order_by(ProviderStaff.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items = []
    for u, provider_name in rows:
        items.append(
            {
                "id": u.id,
                "username": u.username,
                "providerId": u.provider_id,
                "providerName": provider_name or "",
                "status": u.status,
                "createdAt": _iso(u.created_at),
                "updatedAt": _iso(u.updated_at),
            }
        )
    return ok(data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


@router.post("/admin/provider-staff")
async def admin_create_provider_staff(
    request: Request,
    body: AdminCreateProviderStaffBody,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    username = body.username.strip()
    provider_id = body.providerId.strip()
    if not username:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "username 不能为空"})
    if not provider_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "providerId 不能为空"})

    password = _gen_password()

    session_factory = get_session_factory()
    async with session_factory() as session:
        provider = (await session.scalars(select(Provider).where(Provider.id == provider_id).limit(1))).first()
        if provider is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "provider 不存在"})

        existing_pu = (await session.scalars(select(ProviderUser).where(ProviderUser.username == username).limit(1))).first()
        if existing_pu is not None:
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "username 已存在"})
        existing_ps = (await session.scalars(select(ProviderStaff).where(ProviderStaff.username == username).limit(1))).first()
        if existing_ps is not None:
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "username 已存在"})

        staff_id = str(uuid4())
        session.add(
            ProviderStaff(
                id=staff_id,
                provider_id=provider_id,
                username=username,
                password_hash=hash_password(password=password),
                status="ACTIVE",
            )
        )
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.CREATE.value,
                resource_type="PROVIDER_STAFF",
                resource_id=staff_id,
                summary=f"ADMIN 创建 ProviderStaff 账号：{username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": staff_id,
                    "providerId": provider_id,
                    "providerName": provider.name if provider is not None else "",
                    "username": username,
                    "passwordReturnedOnce": True,
                },
            )
        )
        await session.commit()

    return ok(
        data={
            "providerStaff": {
                "id": staff_id,
                "username": username,
                "providerId": provider_id,
                "providerName": provider.name,
                "status": "ACTIVE",
            },
            "password": password,
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/provider-staff/{id}/reset-password")
async def admin_reset_provider_staff_password(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    password = _gen_password()
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(ProviderStaff).where(ProviderStaff.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() != "ACTIVE":
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "账号未启用，不能重置密码"})
        u.password_hash = hash_password(password=password)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="PROVIDER_STAFF",
                resource_id=u.id,
                summary=f"ADMIN 重置 ProviderStaff 账号密码：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "providerId": u.provider_id,
                    "username": u.username,
                    "passwordReturnedOnce": True,
                },
            )
        )
        await session.commit()

        provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
        provider_name = provider.name if provider is not None else ""

    return ok(
        data={
            "providerStaff": {
                "id": u.id,
                "username": u.username,
                "providerId": u.provider_id,
                "providerName": provider_name,
                "status": u.status,
            },
            "password": password,
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/provider-staff/{id}/suspend")
async def admin_suspend_provider_staff(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(ProviderStaff).where(ProviderStaff.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() == "SUSPENDED":
            provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
            provider_name = provider.name if provider is not None else ""
            return ok(
                data={
                    "providerStaff": {
                        "id": u.id,
                        "username": u.username,
                        "providerId": u.provider_id,
                        "providerName": provider_name,
                        "status": u.status,
                    }
                },
                request_id=request.state.request_id,
            )
        before = u.status
        u.status = "SUSPENDED"
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="PROVIDER_STAFF",
                resource_id=u.id,
                summary=f"ADMIN 禁用 ProviderStaff 账号：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "providerId": u.provider_id,
                    "username": u.username,
                    "beforeStatus": before,
                    "afterStatus": u.status,
                },
            )
        )
        await session.commit()
        provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
        provider_name = provider.name if provider is not None else ""
    return ok(
        data={
            "providerStaff": {
                "id": u.id,
                "username": u.username,
                "providerId": u.provider_id,
                "providerName": provider_name,
                "status": u.status,
            }
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/provider-staff/{id}/activate")
async def admin_activate_provider_staff(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(ProviderStaff).where(ProviderStaff.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() == "ACTIVE":
            provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
            provider_name = provider.name if provider is not None else ""
            return ok(
                data={
                    "providerStaff": {
                        "id": u.id,
                        "username": u.username,
                        "providerId": u.provider_id,
                        "providerName": provider_name,
                        "status": u.status,
                    }
                },
                request_id=request.state.request_id,
            )
        before = u.status
        u.status = "ACTIVE"
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="PROVIDER_STAFF",
                resource_id=u.id,
                summary=f"ADMIN 启用 ProviderStaff 账号：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "providerId": u.provider_id,
                    "username": u.username,
                    "beforeStatus": before,
                    "afterStatus": u.status,
                },
            )
        )
        await session.commit()
        provider = (await session.scalars(select(Provider).where(Provider.id == u.provider_id).limit(1))).first()
        provider_name = provider.name if provider is not None else ""
    return ok(
        data={
            "providerStaff": {
                "id": u.id,
                "username": u.username,
                "providerId": u.provider_id,
                "providerName": provider_name,
                "status": u.status,
            }
        },
        request_id=request.state.request_id,
    )


@router.get("/admin/dealer-users")
async def admin_list_dealer_users(
    request: Request,
    _admin=Depends(require_admin),
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(DealerUser, Dealer.name).join(Dealer, Dealer.id == DealerUser.dealer_id, isouter=True)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(DealerUser.username.like(kw) | Dealer.name.like(kw))

    stmt = stmt.order_by(DealerUser.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items = []
    for u, dealer_name in rows:
        items.append(
            {
                "id": u.id,
                "username": u.username,
                "dealerId": u.dealer_id,
                "dealerName": dealer_name or "",
                "status": u.status,
                "createdAt": _iso(u.created_at),
                "updatedAt": _iso(u.updated_at),
            }
        )
    return ok(data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


@router.post("/admin/dealer-users")
async def admin_create_dealer_user(
    request: Request,
    body: AdminCreateDealerUserBody,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    username = body.username.strip()
    dealer_name = body.dealerName.strip()
    if not username:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "username 不能为空"})
    if not dealer_name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerName 不能为空"})

    password = _gen_password()

    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = (await session.scalars(select(DealerUser).where(DealerUser.username == username).limit(1))).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail={"code": "ALREADY_EXISTS", "message": "username 已存在"})

        dealer_id = str(uuid4())
        user_id = str(uuid4())
        session.add(
            Dealer(
                id=dealer_id,
                name=dealer_name,
                status="ACTIVE",
            )
        )
        session.add(
            DealerUser(
                id=user_id,
                dealer_id=dealer_id,
                username=username,
                password_hash=hash_password(password=password),
                status="ACTIVE",
            )
        )
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.CREATE.value,
                resource_type="DEALER_USER",
                resource_id=user_id,
                summary=f"ADMIN 创建 Dealer 账号：{username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": user_id,
                    "dealerId": dealer_id,
                    "dealerName": dealer_name,
                    "username": username,
                    "passwordReturnedOnce": True,
                },
            )
        )
        await session.commit()

    return ok(
        data={
            "dealerUser": {
                "id": user_id,
                "username": username,
                "dealerId": dealer_id,
                "dealerName": dealer_name,
                "status": "ACTIVE",
            },
            "password": password,
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/dealer-users/{id}/reset-password")
async def admin_reset_dealer_user_password(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    admin_id = str(_admin.sub)
    password = _gen_password()
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(DealerUser).where(DealerUser.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() != "ACTIVE":
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "账号未启用，不能重置密码"})
        u.password_hash = hash_password(password=password)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="DEALER_USER",
                resource_id=u.id,
                summary=f"ADMIN 重置 Dealer 账号密码：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "dealerId": u.dealer_id,
                    "username": u.username,
                    "passwordReturnedOnce": True,
                },
            )
        )
        await session.commit()

        dealer = (await session.scalars(select(Dealer).where(Dealer.id == u.dealer_id).limit(1))).first()
        dealer_name = dealer.name if dealer is not None else ""

    return ok(
        data={
            "dealerUser": {
                "id": u.id,
                "username": u.username,
                "dealerId": u.dealer_id,
                "dealerName": dealer_name,
                "status": u.status,
            },
            "password": password,
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/dealer-users/{id}/suspend")
async def admin_suspend_dealer_user(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    """冻结 DealerUser（v1 最小）：仅切换状态，不影响历史数据。冻结后禁止登录与发起新业务。"""
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(DealerUser).where(DealerUser.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() == "SUSPENDED":
            dealer = (await session.scalars(select(Dealer).where(Dealer.id == u.dealer_id).limit(1))).first()
            dealer_name = dealer.name if dealer is not None else ""
            return ok(
                data={
                    "dealerUser": {
                        "id": u.id,
                        "username": u.username,
                        "dealerId": u.dealer_id,
                        "dealerName": dealer_name,
                        "status": u.status,
                    }
                },
                request_id=request.state.request_id,
            )
        before = u.status
        u.status = "SUSPENDED"
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="DEALER_USER",
                resource_id=u.id,
                summary=f"ADMIN 冻结 Dealer 账号：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "dealerId": u.dealer_id,
                    "username": u.username,
                    "beforeStatus": before,
                    "afterStatus": u.status,
                },
            )
        )
        await session.commit()
        dealer = (await session.scalars(select(Dealer).where(Dealer.id == u.dealer_id).limit(1))).first()
        dealer_name = dealer.name if dealer is not None else ""
    return ok(
        data={
            "dealerUser": {
                "id": u.id,
                "username": u.username,
                "dealerId": u.dealer_id,
                "dealerName": dealer_name,
                "status": u.status,
            }
        },
        request_id=request.state.request_id,
    )


@router.post("/admin/dealer-users/{id}/activate")
async def admin_activate_dealer_user(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    """启用 DealerUser（v1 最小）：仅切换状态。"""
    admin_id = str(_admin.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        u = (await session.scalars(select(DealerUser).where(DealerUser.id == id).limit(1))).first()
        if u is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "账号不存在"})
        if str(u.status or "").upper() == "ACTIVE":
            dealer = (await session.scalars(select(Dealer).where(Dealer.id == u.dealer_id).limit(1))).first()
            dealer_name = dealer.name if dealer is not None else ""
            return ok(
                data={
                    "dealerUser": {
                        "id": u.id,
                        "username": u.username,
                        "dealerId": u.dealer_id,
                        "dealerName": dealer_name,
                        "status": u.status,
                    }
                },
                request_id=request.state.request_id,
            )
        before = u.status
        u.status = "ACTIVE"
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="DEALER_USER",
                resource_id=u.id,
                summary=f"ADMIN 启用 Dealer 账号：{u.username}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "targetUserId": u.id,
                    "dealerId": u.dealer_id,
                    "username": u.username,
                    "beforeStatus": before,
                    "afterStatus": u.status,
                },
            )
        )
        await session.commit()
        dealer = (await session.scalars(select(Dealer).where(Dealer.id == u.dealer_id).limit(1))).first()
        dealer_name = dealer.name if dealer is not None else ""
    return ok(
        data={
            "dealerUser": {
                "id": u.id,
                "username": u.username,
                "dealerId": u.dealer_id,
                "dealerName": dealer_name,
                "status": u.status,
            }
        },
        request_id=request.state.request_id,
    )

