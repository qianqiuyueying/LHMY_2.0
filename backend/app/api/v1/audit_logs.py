"""审计日志查询（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 审计日志（AuditLog）数据模型
- specs/health-services-platform/design.md -> E-5 全局审计日志查询（v1 最小契约）
- specs/health-services-platform/tasks.md -> 阶段10-59.2/59.3
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["admin-audit-logs"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return parts[1].strip()


async def _require_admin(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_admin_token(token=token)
    redis = get_redis()
    if await redis.exists(token_blacklist_key(jti=str(payload["jti"]))):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return payload


def _parse_dt(raw: str, *, field_name: str) -> datetime:
    try:
        if len(raw) == 10:
            return datetime.fromisoformat(raw + "T00:00:00")
        return datetime.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}) from exc


def _mask_sensitive(value: Any) -> Any:
    """v1：出参兜底脱敏（避免历史脏数据在 metadata 中泄露）。"""
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for k, v in value.items():
            lk = str(k).lower()
            if lk in {"password", "password_hash", "token", "authorization", "smscode", "sms_code"}:
                masked[k] = "***"
            elif lk in {"phone", "mobile"} and isinstance(v, str):
                s = v.strip()
                masked[k] = f"{s[:3]}****{s[-4:]}" if len(s) >= 7 else None
            else:
                masked[k] = _mask_sensitive(v)
        return masked
    if isinstance(value, list):
        return [_mask_sensitive(x) for x in value]
    return value


def _dto(x: AuditLog) -> dict[str, Any]:
    return {
        "id": x.id,
        "actorType": x.actor_type,
        "actorId": x.actor_id,
        "action": x.action,
        "resourceType": x.resource_type,
        "resourceId": x.resource_id,
        "summary": x.summary,
        "ip": x.ip,
        "userAgent": x.user_agent,
        "metadata": _mask_sensitive(x.metadata_json) if x.metadata_json else None,
        "createdAt": x.created_at.astimezone().isoformat(),
    }


@router.get("/admin/audit-logs")
async def admin_list_audit_logs(
    request: Request,
    authorization: str | None = Header(default=None),
    actorType: Literal["ADMIN", "USER", "DEALER", "PROVIDER", "PROVIDER_STAFF"] | None = None,
    actorId: str | None = None,
    action: Literal["CREATE", "UPDATE", "PUBLISH", "OFFLINE", "APPROVE", "REJECT", "LOGIN", "LOGOUT"] | None = None,
    resourceType: str | None = None,
    resourceId: str | None = None,
    keyword: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    await _require_admin(authorization)

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(AuditLog)
    if actorType:
        stmt = stmt.where(AuditLog.actor_type == str(actorType))
    if actorId and actorId.strip():
        stmt = stmt.where(AuditLog.actor_id == actorId.strip())
    if action:
        stmt = stmt.where(AuditLog.action == str(action))
    if resourceType and resourceType.strip():
        stmt = stmt.where(AuditLog.resource_type == resourceType.strip())
    if resourceId and resourceId.strip():
        stmt = stmt.where(AuditLog.resource_id == resourceId.strip())
    if keyword and keyword.strip():
        stmt = stmt.where(AuditLog.summary.like(f"%{keyword.strip()}%"))
    if dateFrom:
        stmt = stmt.where(AuditLog.created_at >= _parse_dt(str(dateFrom), field_name="dateFrom"))
    if dateTo:
        stmt = stmt.where(AuditLog.created_at <= _parse_dt(str(dateTo), field_name="dateTo"))

    stmt = stmt.order_by(AuditLog.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        logs = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_dto(x) for x in logs], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )

