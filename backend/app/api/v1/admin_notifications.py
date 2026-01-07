"""Admin 顶栏通知接口（v1 最小可执行）。

规格来源：
- specs/mini-program2.0/backend-agent-tasks.md -> BE-ADMIN-002
- specs/health-services-platform/design.md -> Notification 模型

接口：
- GET /api/v1/admin/notifications
- POST /api/v1/admin/notifications/{id}/read
 - POST /api/v1/admin/notifications/send

说明：
- v1 仅支持 ADMIN 自己的站内通知（receiverType=ADMIN, receiverId=adminId）。
- v1.1：支持 Admin 手工发送（群发/定向），并保留原有读取接口兼容。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.dealer_user import DealerUser
from app.models.enums import AuditAction, AuditActorType, NotificationCategory, NotificationReceiverType, NotificationStatus
from app.models.notification import Notification
from app.models.provider_staff import ProviderStaff
from app.models.provider_user import ProviderUser
from app.services.idempotency import IdemActorType, IdempotencyCachedResult, IdempotencyService
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.redis_client import get_redis
from app.utils.response import fail, ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-notifications"])

_SEND_OPERATION = "admin_send_notifications"
_SEND_RATE_LIMIT_MAX = 20
_SEND_RATE_LIMIT_WINDOW_SECONDS = 10 * 60
_SEND_TARGETS_COUNT_MAX = 5000


def _mask_phone(phone: str | None) -> str | None:
    # 与 auth.py 中口径保持一致（仅用于将来可能拼接通知内容时的复用）。
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


def _notification_dto(n: Notification) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "category": getattr(n, "category", None) or NotificationCategory.SYSTEM.value,
        "status": n.status,
        "createdAt": _iso(n.created_at),
        "readAt": _iso(n.read_at),
    }


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return idempotency_key.strip()


async def _idempotency_replay_if_exists(
    *,
    request: Request,
    operation: str,
    actor_type: IdemActorType,
    actor_id: str,
    idempotency_key: str,
) -> JSONResponse | None:
    idem = IdempotencyService(get_redis())
    cached = await idem.get(operation=operation, actor_type=actor_type, actor_id=actor_id, idempotency_key=idempotency_key)
    if cached is None:
        return None

    if cached.success:
        payload = ok(data=cached.data, request_id=request.state.request_id)
    else:
        err = cached.error or {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "details": None}
        payload = fail(
            code=str(err.get("code", "INTERNAL_ERROR")),
            message=str(err.get("message", "服务器内部错误")),
            details=err.get("details"),
            request_id=request.state.request_id,
        )
    return JSONResponse(status_code=int(cached.status_code), content=payload)


async def _enforce_send_rate_limit(*, admin_id: str) -> None:
    """每 ADMIN 20 次 / 10min，超出 429 RATE_LIMITED（你已拍板）。"""

    r = get_redis()
    key = f"rate:admin_notifications_send:{admin_id}"
    n = int(await r.incr(key))
    if n == 1:
        await r.expire(key, _SEND_RATE_LIMIT_WINDOW_SECONDS)
    if n > _SEND_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "操作太频繁，请稍后重试"})


@router.get("/admin/notifications")
async def admin_list_notifications(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    status: Literal["UNREAD", "READ"] | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Notification).where(
        Notification.receiver_type == NotificationReceiverType.ADMIN.value,
        Notification.receiver_id == str(_admin.sub),
    )

    if status:
        if status not in {NotificationStatus.UNREAD.value, NotificationStatus.READ.value}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})
        stmt = stmt.where(Notification.status == str(status))

    stmt = stmt.order_by(Notification.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_notification_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.post("/admin/notifications/{id}/read")
async def admin_mark_notification_read(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin),
):
    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        n = (
            await session.scalars(
                select(Notification)
                .where(
                    Notification.id == id,
                    Notification.receiver_type == NotificationReceiverType.ADMIN.value,
                    Notification.receiver_id == str(_admin.sub),
                )
                .limit(1)
            )
        ).first()

        if n is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "通知不存在"})

        # 幂等：重复标记已读不报错
        if n.status != NotificationStatus.READ.value:
            n.status = NotificationStatus.READ.value
            n.read_at = now
            await session.commit()
            await session.refresh(n)

    return ok(data=_notification_dto(n), request_id=request.state.request_id)


class _AudienceTarget(BaseModel):
    receiverType: Literal["ADMIN", "DEALER", "PROVIDER", "PROVIDER_STAFF"] = Field(..., description="接收者类型")
    receiverId: str = Field(..., min_length=1, description="接收者账号ID")


class _Audience(BaseModel):
    mode: Literal["ALL_ADMINS", "ALL_DEALERS", "ALL_PROVIDERS", "TARGETED"] = Field(..., description="发送范围模式")
    targets: list[_AudienceTarget] | None = Field(default=None, description="定向目标（mode=TARGETED 必填）")


class SendBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1, max_length=4000)
    category: Literal["SYSTEM", "ACTIVITY", "OPS"] = Field(default=NotificationCategory.SYSTEM.value)
    audience: _Audience


async def _resolve_targets(*, session, targets: list[_AudienceTarget]) -> list[tuple[str, str]]:
    """返回 (receiver_type, receiver_id) 列表；不存在/非 ACTIVE 直接报错。"""

    out: list[tuple[str, str]] = []
    for t in targets:
        rt = str(t.receiverType)
        rid = str(t.receiverId or "").strip()
        if not rid:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "receiverId 不能为空"})

        if rt == NotificationReceiverType.ADMIN.value:
            row = (await session.scalars(select(Admin).where(Admin.id == rid).limit(1))).first()
            if row is None or row.status != "ACTIVE":
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"ADMIN 账号不存在或不可用：{rid}"})
        elif rt == NotificationReceiverType.DEALER.value:
            row = (await session.scalars(select(DealerUser).where(DealerUser.id == rid).limit(1))).first()
            if row is None or row.status != "ACTIVE":
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"DEALER 账号不存在或不可用：{rid}"})
        elif rt == NotificationReceiverType.PROVIDER.value:
            row = (await session.scalars(select(ProviderUser).where(ProviderUser.id == rid).limit(1))).first()
            if row is None or row.status != "ACTIVE":
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"PROVIDER 账号不存在或不可用：{rid}"})
        elif rt == NotificationReceiverType.PROVIDER_STAFF.value:
            row = (await session.scalars(select(ProviderStaff).where(ProviderStaff.id == rid).limit(1))).first()
            if row is None or row.status != "ACTIVE":
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"PROVIDER_STAFF 账号不存在或不可用：{rid}"})
        else:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"receiverType 不合法：{rt}"})

        out.append((rt, rid))

    # 去重
    uniq: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    return uniq


@router.post("/admin/notifications/send")
async def admin_send_notifications(
    request: Request,
    body: SendBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation=_SEND_OPERATION,
        actor_type="ADMIN",
        actor_id=str(_admin.sub),
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    mode = str(body.audience.mode)
    if mode == "TARGETED":
        if not body.audience.targets or len(body.audience.targets) < 1:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "TARGETED 模式 targets 不能为空"})
        if len(body.audience.targets) > _SEND_TARGETS_COUNT_MAX:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_ARGUMENT",
                    "message": f"targetsCount 超限：最多 {_SEND_TARGETS_COUNT_MAX}",
                },
            )

    # 非重放请求：计入限流
    await _enforce_send_rate_limit(admin_id=str(_admin.sub))

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 1) 解析接收者列表（fan-out 写入）
        receivers: list[tuple[str, str]] = []
        if mode == "ALL_ADMINS":
            items = (await session.scalars(select(Admin).where(Admin.status == "ACTIVE"))).all()
            receivers = [(NotificationReceiverType.ADMIN.value, x.id) for x in items]
        elif mode == "ALL_DEALERS":
            items = (await session.scalars(select(DealerUser).where(DealerUser.status == "ACTIVE"))).all()
            receivers = [(NotificationReceiverType.DEALER.value, x.id) for x in items]
        elif mode == "ALL_PROVIDERS":
            users = (await session.scalars(select(ProviderUser).where(ProviderUser.status == "ACTIVE"))).all()
            staffs = (await session.scalars(select(ProviderStaff).where(ProviderStaff.status == "ACTIVE"))).all()
            receivers = [(NotificationReceiverType.PROVIDER.value, x.id) for x in users] + [
                (NotificationReceiverType.PROVIDER_STAFF.value, x.id) for x in staffs
            ]
        else:
            receivers = await _resolve_targets(session=session, targets=body.audience.targets or [])

        if not receivers:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "没有可发送的接收者"})

        if len(receivers) > _SEND_TARGETS_COUNT_MAX:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_ARGUMENT",
                    "message": f"targetsCount 超限：最多 {_SEND_TARGETS_COUNT_MAX}",
                },
            )

        now = datetime.now(tz=UTC)
        receiver_type_counts: dict[str, int] = {}
        for rt, _rid in receivers:
            receiver_type_counts[rt] = int(receiver_type_counts.get(rt, 0)) + 1
        meta = {"audience": {"mode": mode}, "targetsCount": len(receivers), "receiverTypeCounts": receiver_type_counts}

        created = 0
        for rt, rid in receivers:
            session.add(
                Notification(
                    id=str(uuid4()),
                    sender_type=NotificationReceiverType.ADMIN.value,
                    sender_id=str(_admin.sub),
                    receiver_type=rt,
                    receiver_id=rid,
                    title=str(body.title).strip(),
                    content=str(body.content),
                    category=str(body.category),
                    meta_json=meta,
                    status=NotificationStatus.UNREAD.value,
                    created_at=now,
                    read_at=None,
                )
            )
            created += 1

        # 2) 审计（最小）
        batch_id = str(uuid4())
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(_admin.sub),
                action=AuditAction.CREATE.value,
                resource_type="NOTIFICATION_SEND",
                resource_id=batch_id,
                summary="ADMIN 手工发送站内通知",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "idempotencyKeyPrefix": idem_key[:12],
                    "mode": mode,
                    "category": str(body.category),
                    "createdCount": created,
                    "targetsCount": len(receivers),
                    "receiverTypeCounts": receiver_type_counts,
                },
            )
        )

        await session.commit()

    data = {"success": True, "createdCount": created, "batchId": batch_id}
    idem = IdempotencyService(get_redis())
    await idem.set(
        operation=_SEND_OPERATION,
        actor_type="ADMIN",
        actor_id=str(_admin.sub),
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return ok(data=data, request_id=request.state.request_id)
