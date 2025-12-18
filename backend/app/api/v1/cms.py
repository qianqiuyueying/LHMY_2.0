"""CMS 内容服务（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> E-4. CMS 内容模块（栏目/内容/公告，v1 最小契约）
- specs/health-services-platform/design.md -> 数据模型 -> CmsChannel/CmsContent
- specs/health-services-platform/tasks.md -> 阶段9-51/52

覆盖接口：
- GET  /api/v1/mini-program/cms/channels
- GET  /api/v1/mini-program/cms/contents
- GET  /api/v1/mini-program/cms/contents/{id}
- GET  /api/v1/admin/cms/channels
- POST /api/v1/admin/cms/channels
- PUT  /api/v1/admin/cms/channels/{id}
- GET  /api/v1/admin/cms/contents
- POST /api/v1/admin/cms/contents
- PUT  /api/v1/admin/cms/contents/{id}
- POST /api/v1/admin/cms/contents/{id}/publish
- POST /api/v1/admin/cms/contents/{id}/offline
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select

from app.models.cms_channel import CmsChannel
from app.models.cms_content import CmsContent
from app.models.enums import CmsContentStatus, CommonEnabledStatus
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["cms"])


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


def _parse_dt(raw: str) -> datetime:
    try:
        # 允许 YYYY-MM-DD 或 ISO8601（含时分秒/时区）
        if len(raw) == 10:
            return datetime.fromisoformat(raw + "T00:00:00")
        return datetime.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "时间参数不合法"}) from exc


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone().isoformat()


class CmsChannelDTO(BaseModel):
    id: str
    name: str
    sort: int
    status: str
    createdAt: str
    updatedAt: str


def _channel_dto(x: CmsChannel) -> dict:
    return CmsChannelDTO(
        id=x.id,
        name=x.name,
        sort=int(x.sort),
        status=x.status,
        createdAt=_iso(x.created_at) or "",
        updatedAt=_iso(x.updated_at) or "",
    ).model_dump()


class CmsContentDTO(BaseModel):
    id: str
    channelId: str
    title: str
    coverImageUrl: str | None = None
    summary: str | None = None
    contentHtml: str
    status: str
    publishedAt: str | None = None
    effectiveFrom: str | None = None
    effectiveUntil: str | None = None
    createdAt: str
    updatedAt: str


def _content_dto(x: CmsContent) -> dict:
    return CmsContentDTO(
        id=x.id,
        channelId=x.channel_id,
        title=x.title,
        coverImageUrl=x.cover_image_url,
        summary=x.summary,
        contentHtml=x.content_html,
        status=x.status,
        publishedAt=_iso(x.published_at),
        effectiveFrom=_iso(x.effective_from),
        effectiveUntil=_iso(x.effective_until),
        createdAt=_iso(x.created_at) or "",
        updatedAt=_iso(x.updated_at) or "",
    ).model_dump()


@router.get("/mini-program/cms/channels")
async def mini_program_list_cms_channels(request: Request):
    # 规格：仅返回 status=ENABLED
    session_factory = get_session_factory()
    async with session_factory() as session:
        items = (
            await session.scalars(
                select(CmsChannel)
                .where(CmsChannel.status == CommonEnabledStatus.ENABLED.value)
                .order_by(CmsChannel.sort.asc(), CmsChannel.created_at.asc())
            )
        ).all()
    return ok(data={"items": [_channel_dto(x) for x in items]}, request_id=request.state.request_id)


@router.get("/mini-program/cms/contents")
async def mini_program_list_cms_contents(
    request: Request,
    channelId: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    # 规格：仅返回 status=PUBLISHED 且在有效期内
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))
    now = datetime.utcnow()

    effective_cond = and_(
        or_(CmsContent.effective_from.is_(None), CmsContent.effective_from <= now),
        or_(CmsContent.effective_until.is_(None), CmsContent.effective_until >= now),
    )

    stmt = select(CmsContent).where(CmsContent.status == CmsContentStatus.PUBLISHED.value, effective_cond)
    if channelId:
        stmt = stmt.where(CmsContent.channel_id == str(channelId))
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(CmsContent.title.like(kw), CmsContent.summary.like(kw)))

    stmt = stmt.order_by(CmsContent.published_at.desc().nullslast(), CmsContent.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        items = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    # 规格：列表 item 字段收敛
    data_items = [
        {
            "id": x.id,
            "channelId": x.channel_id,
            "title": x.title,
            "coverImageUrl": x.cover_image_url,
            "summary": x.summary,
            "publishedAt": _iso(x.published_at),
        }
        for x in items
    ]
    return ok(
        data={"items": data_items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.get("/mini-program/cms/contents/{id}")
async def mini_program_get_cms_content_detail(request: Request, id: str):
    # 规格：仅允许访问 status=PUBLISHED 且在有效期内；否则 NOT_FOUND
    now = datetime.utcnow()
    effective_cond = and_(
        or_(CmsContent.effective_from.is_(None), CmsContent.effective_from <= now),
        or_(CmsContent.effective_until.is_(None), CmsContent.effective_until >= now),
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (
            await session.scalars(
                select(CmsContent)
                .where(CmsContent.id == id, CmsContent.status == CmsContentStatus.PUBLISHED.value, effective_cond)
                .limit(1)
            )
        ).first()
    if x is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "内容不存在"})

    return ok(
        data={
            "id": x.id,
            "channelId": x.channel_id,
            "title": x.title,
            "coverImageUrl": x.cover_image_url,
            "summary": x.summary,
            "contentHtml": x.content_html,
            "publishedAt": _iso(x.published_at),
        },
        request_id=request.state.request_id,
    )


@router.get("/admin/cms/channels")
async def admin_list_cms_channels(request: Request, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        items = (await session.scalars(select(CmsChannel).order_by(CmsChannel.sort.asc(), CmsChannel.created_at.asc()))).all()
    return ok(data={"items": [_channel_dto(x) for x in items]}, request_id=request.state.request_id)


class AdminCreateCmsChannelBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    sort: int = 0


@router.post("/admin/cms/channels")
async def admin_create_cms_channel(
    request: Request,
    body: AdminCreateCmsChannelBody,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = CmsChannel(
            id=str(uuid4()),
            name=body.name.strip(),
            sort=int(body.sort or 0),
            status=CommonEnabledStatus.ENABLED.value,
        )
        session.add(x)
        await session.commit()

    return ok(data=_channel_dto(x), request_id=request.state.request_id)


class AdminUpdateCmsChannelBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    sort: int | None = None
    status: Literal["ENABLED", "DISABLED"] | None = None


@router.put("/admin/cms/channels/{id}")
async def admin_update_cms_channel(
    request: Request,
    id: str,
    body: AdminUpdateCmsChannelBody,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (await session.scalars(select(CmsChannel).where(CmsChannel.id == id).limit(1))).first()
        if x is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "栏目不存在"})

        if body.name is not None:
            x.name = body.name.strip()
        if body.sort is not None:
            x.sort = int(body.sort)
        if body.status is not None:
            x.status = str(body.status)
        await session.commit()

    return ok(data=_channel_dto(x), request_id=request.state.request_id)


@router.get("/admin/cms/contents")
async def admin_list_cms_contents(
    request: Request,
    authorization: str | None = Header(default=None),
    channelId: str | None = None,
    status: Literal["DRAFT", "PUBLISHED", "OFFLINE"] | None = None,
    keyword: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    await _require_admin(authorization)

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(CmsContent)
    if channelId:
        stmt = stmt.where(CmsContent.channel_id == str(channelId))
    if status:
        stmt = stmt.where(CmsContent.status == str(status))
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(CmsContent.title.like(kw), CmsContent.summary.like(kw)))
    if dateFrom:
        stmt = stmt.where(CmsContent.created_at >= _parse_dt(str(dateFrom)))
    if dateTo:
        stmt = stmt.where(CmsContent.created_at <= _parse_dt(str(dateTo)))

    stmt = stmt.order_by(CmsContent.updated_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        items = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    data_items = [
        {
            "id": x.id,
            "channelId": x.channel_id,
            "title": x.title,
            "status": x.status,
            "publishedAt": _iso(x.published_at),
            "createdAt": _iso(x.created_at),
            "updatedAt": _iso(x.updated_at),
        }
        for x in items
    ]
    return ok(
        data={"items": data_items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


class AdminCreateCmsContentBody(BaseModel):
    channelId: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=256)
    coverImageUrl: str | None = Field(default=None, max_length=512)
    summary: str | None = Field(default=None, max_length=512)
    contentHtml: str = Field(..., min_length=1)
    effectiveFrom: str | None = None
    effectiveUntil: str | None = None


def _validate_effective_range(effective_from: datetime | None, effective_until: datetime | None) -> None:
    if effective_from is not None and effective_until is not None and effective_from > effective_until:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "effectiveFrom/effectiveUntil 不合法"})


@router.post("/admin/cms/contents")
async def admin_create_cms_content(
    request: Request,
    body: AdminCreateCmsContentBody,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    eff_from = _parse_dt(body.effectiveFrom) if body.effectiveFrom else None
    eff_until = _parse_dt(body.effectiveUntil) if body.effectiveUntil else None
    _validate_effective_range(eff_from, eff_until)

    session_factory = get_session_factory()
    async with session_factory() as session:
        # v1：channelId 必须存在
        channel = (await session.scalars(select(CmsChannel).where(CmsChannel.id == body.channelId).limit(1))).first()
        if channel is None:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "channelId 不存在"})

        x = CmsContent(
            id=str(uuid4()),
            channel_id=str(body.channelId),
            title=body.title.strip(),
            cover_image_url=(body.coverImageUrl.strip() if body.coverImageUrl else None),
            summary=(body.summary.strip() if body.summary else None),
            content_html=body.contentHtml,
            status=CmsContentStatus.DRAFT.value,
            published_at=None,
            effective_from=eff_from,
            effective_until=eff_until,
        )
        session.add(x)
        await session.commit()

    return ok(data=_content_dto(x), request_id=request.state.request_id)


class AdminUpdateCmsContentBody(BaseModel):
    channelId: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=256)
    coverImageUrl: str | None = Field(default=None, max_length=512)
    summary: str | None = Field(default=None, max_length=512)
    contentHtml: str | None = None
    effectiveFrom: str | None = None
    effectiveUntil: str | None = None
    status: Literal["DRAFT", "PUBLISHED", "OFFLINE"] | None = None


async def _apply_status_transition(x: CmsContent, target_status: str) -> None:
    # 规格：
    # - publish：置 PUBLISHED 并写入 publishedAt；若已是 PUBLISHED -> STATE_CONFLICT
    # - offline：置 OFFLINE；仅允许从 PUBLISHED 下线
    # - v1：允许 OFFLINE -> DRAFT 回到草稿继续编辑；不允许 PUBLISHED -> DRAFT
    if target_status == CmsContentStatus.PUBLISHED.value:
        if x.status == CmsContentStatus.PUBLISHED.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "内容已发布"})
        x.status = CmsContentStatus.PUBLISHED.value
        x.published_at = datetime.utcnow()
        return

    if target_status == CmsContentStatus.OFFLINE.value:
        if x.status != CmsContentStatus.PUBLISHED.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "内容状态不允许下线"})
        x.status = CmsContentStatus.OFFLINE.value
        return

    if target_status == CmsContentStatus.DRAFT.value:
        if x.status == CmsContentStatus.PUBLISHED.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "已发布内容不可回退为草稿"})
        x.status = CmsContentStatus.DRAFT.value
        return

    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})


@router.put("/admin/cms/contents/{id}")
async def admin_update_cms_content(
    request: Request,
    id: str,
    body: AdminUpdateCmsContentBody,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    eff_from = _parse_dt(body.effectiveFrom) if body.effectiveFrom else None
    eff_until = _parse_dt(body.effectiveUntil) if body.effectiveUntil else None
    _validate_effective_range(eff_from, eff_until)

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (await session.scalars(select(CmsContent).where(CmsContent.id == id).limit(1))).first()
        if x is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "内容不存在"})

        if body.channelId is not None:
            channel = (await session.scalars(select(CmsChannel).where(CmsChannel.id == str(body.channelId)).limit(1))).first()
            if channel is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "channelId 不存在"})
            x.channel_id = str(body.channelId)
        if body.title is not None:
            x.title = body.title.strip()
        if body.coverImageUrl is not None:
            x.cover_image_url = (body.coverImageUrl.strip() if body.coverImageUrl else None)
        if body.summary is not None:
            x.summary = (body.summary.strip() if body.summary else None)
        if body.contentHtml is not None:
            x.content_html = body.contentHtml
        if body.effectiveFrom is not None:
            x.effective_from = eff_from
        if body.effectiveUntil is not None:
            x.effective_until = eff_until

        if body.status is not None:
            await _apply_status_transition(x, str(body.status))

        await session.commit()

    return ok(data=_content_dto(x), request_id=request.state.request_id)


@router.post("/admin/cms/contents/{id}/publish")
async def admin_publish_cms_content(request: Request, id: str, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (await session.scalars(select(CmsContent).where(CmsContent.id == id).limit(1))).first()
        if x is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "内容不存在"})

        await _apply_status_transition(x, CmsContentStatus.PUBLISHED.value)
        await session.commit()

    return ok(data=_content_dto(x), request_id=request.state.request_id)


@router.post("/admin/cms/contents/{id}/offline")
async def admin_offline_cms_content(request: Request, id: str, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (await session.scalars(select(CmsContent).where(CmsContent.id == id).limit(1))).first()
        if x is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "内容不存在"})

        await _apply_status_transition(x, CmsContentStatus.OFFLINE.value)
        await session.commit()

    return ok(data=_content_dto(x), request_id=request.state.request_id)

