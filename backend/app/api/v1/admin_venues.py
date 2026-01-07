"""Admin 场所管理与审核（阶段12：展示资料提交/审核）。

规格来源：
- specs/health-services-platform/tasks.md -> 阶段12「展示资料提交与审核（v1）」
- specs/health-services-platform/design.md -> Venue.publishStatus（DRAFT/PUBLISHED/OFFLINE）
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType, VenuePublishStatus, VenueReviewStatus
from app.models.provider import Provider
from app.models.venue import Venue
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.services.rbac import ActorContext
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-venues"])


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


def _venue_list_item(*, v: Venue, provider_name: str | None) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "providerId": v.provider_id,
        "providerName": provider_name or "",
        "publishStatus": v.publish_status,
        "reviewStatus": getattr(v, "review_status", None),
        "offlineReason": getattr(v, "offline_reason", None),
        "offlinedAt": _iso(getattr(v, "offlined_at", None)),
        "updatedAt": _iso(v.updated_at),
        "createdAt": _iso(v.created_at),
    }


def _venue_detail_item(*, v: Venue, provider_name: str | None) -> dict:
    return {
        "id": v.id,
        "providerId": v.provider_id,
        "providerName": provider_name or "",
        "name": v.name,
        "address": v.address,
        "contactPhone": v.contact_phone,
        "contactPhoneMasked": _mask_phone(v.contact_phone),
        "businessHours": v.business_hours,
        "countryCode": v.country_code,
        "provinceCode": v.province_code,
        "cityCode": v.city_code,
        "description": v.description,
        "logoUrl": v.logo_url,
        "coverImageUrl": v.cover_image_url,
        "imageUrls": v.image_urls,
        "tags": v.tags,
        "publishStatus": v.publish_status,
        "reviewStatus": getattr(v, "review_status", None),
        "rejectReason": getattr(v, "reject_reason", None),
        "rejectedAt": _iso(getattr(v, "rejected_at", None)),
        "offlineReason": getattr(v, "offline_reason", None),
        "offlinedAt": _iso(getattr(v, "offlined_at", None)),
        "updatedAt": _iso(v.updated_at),
        "createdAt": _iso(v.created_at),
    }


class RejectVenueBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200)

    @model_validator(mode="after")
    def _trim(self):
        self.reason = str(self.reason or "").strip()
        if not self.reason:
            raise ValueError("reason 不能为空")
        return self


class OfflineVenueBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200)

    @model_validator(mode="after")
    def _trim(self):
        self.reason = str(self.reason or "").strip()
        if not self.reason:
            raise ValueError("reason 不能为空")
        return self


@router.get("/admin/venues")
async def admin_list_venues(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    keyword: str | None = None,
    providerId: str | None = None,
    publishStatus: str | None = None,  # DRAFT|PUBLISHED|OFFLINE
    reviewStatus: str | None = None,  # DRAFT|SUBMITTED|APPROVED|REJECTED（v1：用于运营侧筛选）
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Venue)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(Venue.name.like(kw) | Venue.address.like(kw))
    if providerId and providerId.strip():
        stmt = stmt.where(Venue.provider_id == providerId.strip())
    if publishStatus and publishStatus.strip():
        stmt = stmt.where(Venue.publish_status == publishStatus.strip())
    if reviewStatus and reviewStatus.strip():
        rs = reviewStatus.strip()
        allowed = {
            VenueReviewStatus.DRAFT.value,
            VenueReviewStatus.SUBMITTED.value,
            VenueReviewStatus.APPROVED.value,
            VenueReviewStatus.REJECTED.value,
        }
        if rs not in allowed:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "reviewStatus 不合法"})
        stmt = stmt.where(getattr(Venue, "review_status") == rs)

    stmt = stmt.order_by(Venue.updated_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        venues = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()
        provider_ids = list({v.provider_id for v in venues if v.provider_id})
        providers = (
            (await session.scalars(select(Provider).where(Provider.id.in_(provider_ids)))).all() if provider_ids else []
        )
        provider_name_by_id = {p.id: p.name for p in providers}

    return ok(
        data={
            "items": [_venue_list_item(v=x, provider_name=provider_name_by_id.get(x.provider_id)) for x in venues],
            "page": page,
            "pageSize": page_size,
            "total": total,
        },
        request_id=request.state.request_id,
    )


@router.get("/admin/venues/{id}")
async def admin_get_venue_detail(request: Request, id: str, _admin: ActorContext = Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (await session.scalars(select(Venue).where(Venue.id == id).limit(1))).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})
        p = (await session.scalars(select(Provider).where(Provider.id == v.provider_id).limit(1))).first()

        # 规格（TASK-P0-006）：Admin 查看联系方式属于敏感访问，需要审计（不记录电话明文）
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(_admin.sub),
                action="VIEW",
                resource_type="VENUE",
                resource_id=v.id,
                summary=f"ADMIN 查看场所详情（含联系方式）：{v.id}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "view": "VENUE_DETAIL",
                    "includes": ["contactPhone"],
                    "contactPhoneMasked": _mask_phone(v.contact_phone),
                },
            )
        )
        await session.commit()

    return ok(data=_venue_detail_item(v=v, provider_name=(p.name if p else None)), request_id=request.state.request_id)

async def _set_publish_status(
    *,
    request: Request,
    admin_id: str,
    venue_id: str,
    target: str,
    action: str,
    summary: str,
    reason: str | None = None,
):
    if target not in {
        VenuePublishStatus.DRAFT.value,
        VenuePublishStatus.PUBLISHED.value,
        VenuePublishStatus.OFFLINE.value,
    }:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "publishStatus 不合法"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (await session.scalars(select(Venue).where(Venue.id == venue_id).limit(1))).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        # 统一口径：同一目标状态重复提交 -> 200 幂等 no-op（不刷审计）
        if str(v.publish_status or "") == str(target):
            return ok(
                data={"success": True, "publishStatus": str(v.publish_status or target)},
                request_id=request.state.request_id,
            )

        # 你已拍板的非法迁移口径（FLOW-REVIEW-VENUES）：
        # 1) 禁止 DRAFT -> OFFLINE
        # 2) 禁止 PUBLISHED -> DRAFT
        current = str(v.publish_status or "")
        if current == VenuePublishStatus.DRAFT.value and target == VenuePublishStatus.OFFLINE.value:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "非法状态迁移：DRAFT 不能直接下线"},
            )
        if current == VenuePublishStatus.PUBLISHED.value and target == VenuePublishStatus.DRAFT.value:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVALID_STATE_TRANSITION", "message": "非法状态迁移：已发布场所不能直接驳回为草稿"},
            )

        before = v.publish_status
        v.publish_status = target
        # 下线原因：仅 target=OFFLINE 时记录（覆盖式）
        if target == VenuePublishStatus.OFFLINE.value:
            v.offline_reason = str(reason or "").strip() if reason is not None else None
            v.offlined_at = datetime.utcnow()
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=action,
                resource_type="VENUE",
                resource_id=v.id,
                summary=summary,
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "beforePublishStatus": before,
                    "targetPublishStatus": target,
                    "afterPublishStatus": target,
                    **({"reason": getattr(v, "offline_reason", None)} if target == VenuePublishStatus.OFFLINE.value else {}),
                },
            )
        )
        await session.commit()

    return ok(data={"success": True, "publishStatus": target}, request_id=request.state.request_id)


@router.post("/admin/venues/{id}/publish")
async def admin_publish_venue(request: Request, id: str, _admin: ActorContext = Depends(require_admin_phone_bound)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (await session.scalars(select(Venue).where(Venue.id == id).limit(1))).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        # 发布上线允许两种入口：
        # - 旧流程：SUBMITTED -> PUBLISHED（通过并发布）
        # - 新流程：APPROVED -> PUBLISHED（审核通过后，在“内容投放/官网投放”中上线）
        rs = str(getattr(v, "review_status", "") or "")
        if rs not in {VenueReviewStatus.SUBMITTED.value, VenueReviewStatus.APPROVED.value}:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "场所状态不允许发布上线"})

        # 幂等：已发布直接返回
        if str(v.publish_status or "") == VenuePublishStatus.PUBLISHED.value:
            return ok(
                data={"success": True, "publishStatus": VenuePublishStatus.PUBLISHED.value},
                request_id=request.state.request_id,
            )
        # 若为 SUBMITTED：发布时顺带置为 APPROVED；若已 APPROVED：保持不变

        before_publish = str(v.publish_status or "")
        before_review = str(getattr(v, "review_status", "") or "")

        v.publish_status = VenuePublishStatus.PUBLISHED.value
        v.review_status = VenueReviewStatus.APPROVED.value
        v.reject_reason = None
        v.rejected_at = None
        # 发布上线：清理历史“下线原因”（避免已恢复上线仍展示旧下线原因）
        v.offline_reason = None
        v.offlined_at = None

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(_admin.sub),
                action=AuditAction.PUBLISH.value,
                resource_type="VENUE",
                resource_id=v.id,
                summary="ADMIN 审核通过并发布场所展示资料",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "beforePublishStatus": before_publish,
                    "afterPublishStatus": v.publish_status,
                    "beforeReviewStatus": before_review,
                    "afterReviewStatus": v.review_status,
                },
            )
        )
        await session.commit()

    return ok(data={"success": True, "publishStatus": VenuePublishStatus.PUBLISHED.value}, request_id=request.state.request_id)


@router.post("/admin/venues/{id}/approve")
async def admin_approve_venue(request: Request, id: str, _admin: ActorContext = Depends(require_admin_phone_bound)):
    """审核通过（不发布）。

    终态口径：审核与对外发布解耦；发布上线应在“内容与投放/官网投放”完成。
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (await session.scalars(select(Venue).where(Venue.id == id).limit(1))).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        rs = str(getattr(v, "review_status", "") or "")
        if rs == VenueReviewStatus.APPROVED.value:
            return ok(data={"success": True, "reviewStatus": VenueReviewStatus.APPROVED.value}, request_id=request.state.request_id)
        if rs != VenueReviewStatus.SUBMITTED.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "场所状态不允许审核通过"})

        before_review = rs
        v.review_status = VenueReviewStatus.APPROVED.value
        v.reject_reason = None
        v.rejected_at = None

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(_admin.sub),
                action=AuditAction.APPROVE.value,
                resource_type="VENUE",
                resource_id=v.id,
                summary="ADMIN 审核通过场所展示资料（不发布）",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "beforeReviewStatus": before_review,
                    "afterReviewStatus": v.review_status,
                },
            )
        )
        await session.commit()

    return ok(data={"success": True, "reviewStatus": VenueReviewStatus.APPROVED.value}, request_id=request.state.request_id)


@router.post("/admin/venues/{id}/reject")
async def admin_reject_venue(
    request: Request,
    id: str,
    body: RejectVenueBody,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    session_factory = get_session_factory()
    async with session_factory() as session:
        v = (await session.scalars(select(Venue).where(Venue.id == id).limit(1))).first()
        if v is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "场所不存在"})

        if str(getattr(v, "review_status", "") or "") != VenueReviewStatus.SUBMITTED.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "场所状态不允许驳回"})
        # 容错：历史/并发可能导致 publish_status 未同步回 DRAFT（例如从 OFFLINE resubmit）
        # 只要 review_status=SUBMITTED 且未处于 PUBLISHED，则允许驳回并把 publish_status 归一到 DRAFT，避免僵尸状态。
        if str(v.publish_status or "") == VenuePublishStatus.PUBLISHED.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "已发布场所不允许驳回，请先下线"})

        before_review = str(getattr(v, "review_status", "") or "")
        v.publish_status = VenuePublishStatus.DRAFT.value
        v.review_status = VenueReviewStatus.REJECTED.value
        v.reject_reason = str(body.reason or "").strip()
        v.rejected_at = datetime.utcnow()

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(_admin.sub),
                action=AuditAction.REJECT.value,
                resource_type="VENUE",
                resource_id=v.id,
                summary="ADMIN 驳回场所展示资料",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "path": request.url.path,
                    "method": request.method,
                    "requestId": request.state.request_id,
                    "beforeReviewStatus": before_review,
                    "afterReviewStatus": v.review_status,
                    "reason": v.reject_reason,
                },
            )
        )
        await session.commit()

    return ok(data={"success": True, "reviewStatus": VenueReviewStatus.REJECTED.value}, request_id=request.state.request_id)


@router.post("/admin/venues/{id}/offline")
async def admin_offline_venue(
    request: Request,
    id: str,
    body: OfflineVenueBody,
    _admin: ActorContext = Depends(require_admin_phone_bound),
):
    return await _set_publish_status(
        request=request,
        admin_id=str(_admin.sub),
        venue_id=id,
        target=VenuePublishStatus.OFFLINE.value,
        action=AuditAction.OFFLINE.value,
        summary="ADMIN 下线场所展示资料",
        reason=str(body.reason or "").strip(),
    )
