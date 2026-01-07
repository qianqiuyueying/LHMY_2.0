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

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

import bleach
import markdown as mdlib
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.cms_channel import CmsChannel
from app.models.cms_content import CmsContent
from app.models.enums import AuditAction, AuditActorType, CmsContentStatus, CommonEnabledStatus
from app.services.rbac import ActorContext
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["cms"])


_TZ_BEIJING = timezone(timedelta(hours=8))


def _beijing_day_start_to_utc_naive(raw_ymd: str) -> datetime:
    d = datetime.fromisoformat(raw_ymd + "T00:00:00").replace(tzinfo=_TZ_BEIJING)
    return d.astimezone(timezone.utc).replace(tzinfo=None)


def _beijing_day_end_to_utc_naive(raw_ymd: str) -> datetime:
    # inclusive end-of-day: 23:59:59 in Beijing
    d = datetime.fromisoformat(raw_ymd + "T23:59:59").replace(tzinfo=_TZ_BEIJING)
    return d.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_dt_utc_naive(raw: str) -> datetime:
    """Parse ISO8601 or YYYY-MM-DD into naive UTC datetime for DB.

    - ISO8601 may include timezone offset or 'Z' suffix
    - naive datetime (no tzinfo) is treated as UTC (DB contract)
    """
    s = str(raw or "").strip()
    if not s:
        raise ValueError("empty")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_effective_from(raw: str) -> datetime:
    s = str(raw or "").strip()
    if len(s) == 10:
        return _beijing_day_start_to_utc_naive(s)
    return _parse_dt_utc_naive(s)


def _parse_effective_until(raw: str) -> datetime:
    s = str(raw or "").strip()
    if len(s) == 10:
        return _beijing_day_end_to_utc_naive(s)
    return _parse_dt_utc_naive(s)


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
    channelId: str | None = None
    title: str
    coverImageUrl: str | None = None
    summary: str | None = None
    contentHtml: str
    contentMd: str | None = None
    status: str
    publishedAt: str | None = None
    mpStatus: str | None = None
    mpPublishedAt: str | None = None
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
        contentMd=getattr(x, "content_md", None),
        status=x.status,
        publishedAt=_iso(x.published_at),
        mpStatus=getattr(x, "mp_status", None),
        mpPublishedAt=_iso(getattr(x, "mp_published_at", None)),
        effectiveFrom=_iso(x.effective_from),
        effectiveUntil=_iso(x.effective_until),
        createdAt=_iso(x.created_at) or "",
        updatedAt=_iso(x.updated_at) or "",
    ).model_dump()


def _markdown_to_safe_html(raw_md: str) -> str:
    """Markdown -> HTML（并做安全清洗）。

    - Markdown 库默认允许内联 HTML，这里统一用 bleach 过滤，避免 XSS
    - 小程序 rich-text 支持的标签有限，但仍建议在写侧统一输出干净 HTML
    """
    text = str(raw_md or "")
    html = mdlib.markdown(
        text,
        extensions=[
            "extra",
            "sane_lists",
            "toc",
            # 支持 ~~删除线~~（与 admin 端 markdown-it 语法对齐）
            "pymdownx.tilde",
        ],
        output_format="html",
    )
    allowed_tags = [
        "p",
        "br",
        "hr",
        "blockquote",
        "pre",
        "code",
        "strong",
        "em",
        "del",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "a",
        "img",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    ]
    allowed_attrs = {
        "a": ["href", "title", "rel"],
        "img": ["src", "alt", "title"],
        "*": [],
    }
    # 只允许 http(s) / 相对链接
    clean = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=["http", "https"],
        strip=True,
    )
    # 对所有链接补 rel（避免 window.opener 等）
    clean = bleach.linkify(clean, callbacks=[bleach.callbacks.nofollow])
    return clean


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


@router.get("/website/cms/channels")
async def website_list_cms_channels(request: Request):
    """官网读侧：栏目列表（与小程序一致，仅 ENABLED）。"""
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
    # v2：仅返回 mp_status=PUBLISHED 且在有效期内
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))
    now = datetime.utcnow()

    effective_cond = and_(
        or_(CmsContent.effective_from.is_(None), CmsContent.effective_from <= now),
        or_(CmsContent.effective_until.is_(None), CmsContent.effective_until >= now),
    )

    mp_status_col = getattr(CmsContent, "mp_status")
    mp_pub_at_col = getattr(CmsContent, "mp_published_at")
    stmt = select(CmsContent).where(mp_status_col == CmsContentStatus.PUBLISHED.value, effective_cond)
    if channelId:
        stmt = stmt.where(CmsContent.channel_id == str(channelId))
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(CmsContent.title.like(kw), CmsContent.summary.like(kw)))

    # 规格意图：按 publishedAt 倒序（无发布时间的排在最后），再按 createdAt 倒序
    # MySQL 不支持 "ORDER BY ... NULLS LAST" 语法，使用布尔表达式实现 nulls last：
    # published_at IS NULL: false(0) 排前、true(1) 排后
    base_stmt = stmt
    stmt = base_stmt.order_by(mp_pub_at_col.is_(None).asc(), mp_pub_at_col.desc(), CmsContent.created_at.desc())
    count_stmt = select(func.count()).select_from(base_stmt.subquery())

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
            "publishedAt": _iso(getattr(x, "mp_published_at", None)),
        }
        for x in items
    ]
    return ok(
        data={"items": data_items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.get("/website/cms/contents")
async def website_list_cms_contents(
    request: Request,
    channelId: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    """官网读侧：只返回官网已发布内容（status=PUBLISHED）且在有效期内。"""
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

    base_stmt = stmt
    stmt = base_stmt.order_by(
        CmsContent.published_at.is_(None).asc(), CmsContent.published_at.desc(), CmsContent.created_at.desc()
    )
    count_stmt = select(func.count()).select_from(base_stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        items = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

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
    return ok(data={"items": data_items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


@router.get("/mini-program/cms/contents/{id}")
async def mini_program_get_cms_content_detail(request: Request, id: str):
    # v2：仅允许访问 mp_status=PUBLISHED 且在有效期内；否则 NOT_FOUND
    now = datetime.utcnow()
    effective_cond = and_(
        or_(CmsContent.effective_from.is_(None), CmsContent.effective_from <= now),
        or_(CmsContent.effective_until.is_(None), CmsContent.effective_until >= now),
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        mp_status_col = getattr(CmsContent, "mp_status")
        x = (
            await session.scalars(
                select(CmsContent)
                .where(CmsContent.id == id, mp_status_col == CmsContentStatus.PUBLISHED.value, effective_cond)
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
            "publishedAt": _iso(getattr(x, "mp_published_at", None)),
        },
        request_id=request.state.request_id,
    )


@router.get("/website/cms/contents/{id}")
async def website_get_cms_content_detail(request: Request, id: str):
    """官网读侧：仅允许访问 status=PUBLISHED 且在有效期内；否则 NOT_FOUND。"""
    now = datetime.utcnow()
    effective_cond = and_(
        or_(CmsContent.effective_from.is_(None), CmsContent.effective_from <= now),
        or_(CmsContent.effective_until.is_(None), CmsContent.effective_until >= now),
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (
            await session.scalars(
                select(CmsContent).where(CmsContent.id == id, CmsContent.status == CmsContentStatus.PUBLISHED.value, effective_cond).limit(1)
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
async def admin_list_cms_channels(request: Request, _admin=Depends(require_admin)):

    session_factory = get_session_factory()
    async with session_factory() as session:
        items = (
            await session.scalars(select(CmsChannel).order_by(CmsChannel.sort.asc(), CmsChannel.created_at.asc()))
        ).all()
    return ok(data={"items": [_channel_dto(x) for x in items]}, request_id=request.state.request_id)


class AdminCreateCmsChannelBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    sort: int = 0


@router.post("/admin/cms/channels")
async def admin_create_cms_channel(
    request: Request,
    body: AdminCreateCmsChannelBody,
    _admin=Depends(require_admin),
):

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
    _admin=Depends(require_admin),
):

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
    _admin=Depends(require_admin),
    channelId: str | None = None,
    scope: Literal["WEB", "MINI_PROGRAM"] | None = None,
    status: Literal["DRAFT", "PUBLISHED", "OFFLINE"] | None = None,
    keyword: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    includeContent: bool = True,
    page: int = 1,
    pageSize: int = 20,
):

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(CmsContent)
    if channelId:
        stmt = stmt.where(CmsContent.channel_id == str(channelId))
    if status:
        if scope == "MINI_PROGRAM":
            mp_status_col = getattr(CmsContent, "mp_status")
            stmt = stmt.where(mp_status_col == str(status))
        else:
            stmt = stmt.where(CmsContent.status == str(status))
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(CmsContent.title.like(kw), CmsContent.summary.like(kw)))
    # Spec (Admin): dateFrom/dateTo are Beijing natural days (YYYY-MM-DD)
    if dateFrom:
        df = str(dateFrom).strip()
        if len(df) == 10:
            stmt = stmt.where(CmsContent.created_at >= _beijing_day_start_to_utc_naive(df))
        else:
            stmt = stmt.where(CmsContent.created_at >= _parse_dt_utc_naive(df))
    if dateTo:
        dt_s = str(dateTo).strip()
        if len(dt_s) == 10:
            # inclusive end-of-day
            stmt = stmt.where(CmsContent.created_at <= _beijing_day_end_to_utc_naive(dt_s))
        else:
            stmt = stmt.where(CmsContent.created_at <= _parse_dt_utc_naive(dt_s))

    stmt = stmt.order_by(CmsContent.updated_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        items = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    # REQ-P0-004：列表返回 contentHtml 以支持增量编辑
    data_items: list[dict] = []
    for x in items:
        data_items.append(
            {
                "id": x.id,
                "channelId": x.channel_id,
                "title": x.title,
                "coverImageUrl": x.cover_image_url,
                "summary": x.summary,
                "status": x.status,
                "publishedAt": _iso(x.published_at),
                "mpStatus": getattr(x, "mp_status", None),
                "mpPublishedAt": _iso(getattr(x, "mp_published_at", None)),
                "effectiveFrom": _iso(x.effective_from),
                "effectiveUntil": _iso(x.effective_until),
                "createdAt": _iso(x.created_at),
                "updatedAt": _iso(x.updated_at),
                "contentHtml": x.content_html if includeContent else None,
                "contentMd": getattr(x, "content_md", None) if includeContent else None,
            }
        )
    return ok(
        data={"items": data_items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


class AdminCreateCmsContentBody(BaseModel):
    channelId: str | None = Field(default=None)
    title: str = Field(..., min_length=1, max_length=256)
    coverImageUrl: str | None = Field(default=None, max_length=512)
    summary: str | None = Field(default=None, max_length=512)
    contentHtml: str | None = None
    contentMd: str | None = None
    effectiveFrom: str | None = None
    effectiveUntil: str | None = None


def _validate_effective_range(effective_from: datetime | None, effective_until: datetime | None) -> None:
    if effective_from is not None and effective_until is not None and effective_from > effective_until:
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "effectiveFrom/effectiveUntil 不合法"}
        )


@router.post("/admin/cms/contents")
async def admin_create_cms_content(
    request: Request,
    body: AdminCreateCmsContentBody,
    _admin=Depends(require_admin),
):

    eff_from = _parse_effective_from(body.effectiveFrom) if body.effectiveFrom else None
    eff_until = _parse_effective_until(body.effectiveUntil) if body.effectiveUntil else None
    _validate_effective_range(eff_from, eff_until)

    session_factory = get_session_factory()
    async with session_factory() as session:
        # v3：内容中心允许不挂栏目（官网投放页再分配）
        channel_id: str | None = None
        if body.channelId is not None and str(body.channelId).strip():
            channel_id = str(body.channelId).strip()
            channel = (await session.scalars(select(CmsChannel).where(CmsChannel.id == channel_id).limit(1))).first()
            if channel is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "channelId 不存在"})

        content_md = (body.contentMd or "").strip() if body.contentMd is not None else None
        content_html = (body.contentHtml or "").strip() if body.contentHtml is not None else ""
        if content_md:
            content_html = _markdown_to_safe_html(content_md)
        if not content_html:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "正文不能为空（Markdown 或 HTML）"})

        x = CmsContent(
            id=str(uuid4()),
            channel_id=channel_id,
            title=body.title.strip(),
            cover_image_url=(body.coverImageUrl.strip() if body.coverImageUrl else None),
            summary=(body.summary.strip() if body.summary else None),
            content_md=content_md,
            content_html=content_html,
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
    contentMd: str | None = None
    effectiveFrom: str | None = None
    effectiveUntil: str | None = None
    status: Literal["DRAFT", "PUBLISHED", "OFFLINE"] | None = None


def _apply_status_transition(x: CmsContent, target_status: str) -> tuple[bool, str, str]:
    """应用官网（WEB）发布状态迁移。

    规格（specs-prod/admin/api-contracts.md#9G + #1.4）：
    - 同一目标状态重复提交：200 no-op（不抛错）
    - 非法状态迁移：409 INVALID_STATE_TRANSITION
    - PUBLISHED -> DRAFT 禁止
    - OFFLINE 仅允许从 PUBLISHED 下线
    """

    before = str(x.status or "")

    if target_status == CmsContentStatus.PUBLISHED.value:
        if before == CmsContentStatus.PUBLISHED.value:
            return False, before, before
        x.status = CmsContentStatus.PUBLISHED.value
        if x.published_at is None:
            x.published_at = datetime.utcnow()
        return True, before, CmsContentStatus.PUBLISHED.value

    if target_status == CmsContentStatus.OFFLINE.value:
        if before == CmsContentStatus.OFFLINE.value:
            return False, before, before
        if before != CmsContentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": "内容状态不允许下线"}
            )
        x.status = CmsContentStatus.OFFLINE.value
        return True, before, CmsContentStatus.OFFLINE.value

    if target_status == CmsContentStatus.DRAFT.value:
        if before == CmsContentStatus.DRAFT.value:
            return False, before, before
        if before == CmsContentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": "已发布内容不可回退为草稿"}
            )
        x.status = CmsContentStatus.DRAFT.value
        return True, before, CmsContentStatus.DRAFT.value

    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})


def _apply_mp_status_transition(x: CmsContent, target_status: str) -> tuple[bool, str, str]:
    """应用小程序（MINI_PROGRAM）发布状态迁移。规则与 WEB 一致。"""

    before = str(getattr(x, "mp_status", CmsContentStatus.DRAFT.value) or "")

    if target_status == CmsContentStatus.PUBLISHED.value:
        if before == CmsContentStatus.PUBLISHED.value:
            return False, before, before
        setattr(x, "mp_status", CmsContentStatus.PUBLISHED.value)
        if getattr(x, "mp_published_at", None) is None:
            setattr(x, "mp_published_at", datetime.utcnow())
        return True, before, CmsContentStatus.PUBLISHED.value

    if target_status == CmsContentStatus.OFFLINE.value:
        if before == CmsContentStatus.OFFLINE.value:
            return False, before, before
        if before != CmsContentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": "内容小程序状态不允许下线"}
            )
        setattr(x, "mp_status", CmsContentStatus.OFFLINE.value)
        return True, before, CmsContentStatus.OFFLINE.value

    if target_status == CmsContentStatus.DRAFT.value:
        if before == CmsContentStatus.DRAFT.value:
            return False, before, before
        if before == CmsContentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": "小程序已发布内容不可回退为草稿"}
            )
        setattr(x, "mp_status", CmsContentStatus.DRAFT.value)
        return True, before, CmsContentStatus.DRAFT.value

    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})


@router.put("/admin/cms/contents/{id}")
async def admin_update_cms_content(
    request: Request,
    id: str,
    body: AdminUpdateCmsContentBody,
    _admin=Depends(require_admin),
):

    eff_from = _parse_effective_from(body.effectiveFrom) if body.effectiveFrom else None
    eff_until = _parse_effective_until(body.effectiveUntil) if body.effectiveUntil else None
    _validate_effective_range(eff_from, eff_until)

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (await session.scalars(select(CmsContent).where(CmsContent.id == id).limit(1))).first()
        if x is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "内容不存在"})

        if body.channelId is not None:
            raw = str(body.channelId).strip()
            if not raw:
                x.channel_id = None
            else:
                channel = (await session.scalars(select(CmsChannel).where(CmsChannel.id == raw).limit(1))).first()
                if channel is None:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "channelId 不存在"})
                x.channel_id = raw
        if body.title is not None:
            x.title = body.title.strip()
        if body.coverImageUrl is not None:
            x.cover_image_url = body.coverImageUrl.strip() if body.coverImageUrl else None
        if body.summary is not None:
            x.summary = body.summary.strip() if body.summary else None
        if body.contentHtml is not None:
            x.content_html = body.contentHtml
            # 兼容：若直接改 HTML，则清空 markdown（避免双源不一致）
            x.content_md = None
        if body.contentMd is not None:
            content_md = body.contentMd.strip() if body.contentMd else ""
            if not content_md:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "contentMd 不能为空"})
            x.content_md = content_md
            x.content_html = _markdown_to_safe_html(content_md)
        if body.effectiveFrom is not None:
            x.effective_from = eff_from
        if body.effectiveUntil is not None:
            x.effective_until = eff_until

        if body.status is not None:
            _apply_status_transition(x, str(body.status))

        await session.commit()

    return ok(data=_content_dto(x), request_id=request.state.request_id)


@router.post("/admin/cms/contents/{id}/publish")
async def admin_publish_cms_content(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
    scope: Literal["WEB", "MINI_PROGRAM"] = "WEB",
):

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (await session.scalars(select(CmsContent).where(CmsContent.id == id).limit(1))).first()
        if x is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "内容不存在"})

        if scope == "MINI_PROGRAM":
            changed, before, after = _apply_mp_status_transition(x, CmsContentStatus.PUBLISHED.value)
        else:
            # v3：官网投放要求已分配栏目（栏目仅用于官网）
            if not (x.channel_id or "").strip():
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "官网投放必须先设置栏目"})
            changed, before, after = _apply_status_transition(x, CmsContentStatus.PUBLISHED.value)

        # 幂等 no-op：不刷审计
        if changed:
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.ADMIN.value,
                    actor_id=str(_admin.sub),
                    action=AuditAction.PUBLISH.value,
                    resource_type="CMS_CONTENT",
                    resource_id=x.id,
                    summary=f"ADMIN 发布 CMS 内容（{scope}）：{x.title}",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={
                        "path": request.url.path,
                        "method": request.method,
                        "requestId": request.state.request_id,
                        "scope": scope,
                        "beforeStatus": before,
                        "afterStatus": after,
                        "channelId": x.channel_id,
                    },
                )
            )
        await session.commit()

    return ok(data=_content_dto(x), request_id=request.state.request_id)


@router.post("/admin/cms/contents/{id}/offline")
async def admin_offline_cms_content(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin_phone_bound),
    scope: Literal["WEB", "MINI_PROGRAM"] = "WEB",
):

    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (await session.scalars(select(CmsContent).where(CmsContent.id == id).limit(1))).first()
        if x is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "内容不存在"})

        if scope == "MINI_PROGRAM":
            changed, before, after = _apply_mp_status_transition(x, CmsContentStatus.OFFLINE.value)
        else:
            changed, before, after = _apply_status_transition(x, CmsContentStatus.OFFLINE.value)

        if changed:
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.ADMIN.value,
                    actor_id=str(_admin.sub),
                    action=AuditAction.OFFLINE.value,
                    resource_type="CMS_CONTENT",
                    resource_id=x.id,
                    summary=f"ADMIN 下线 CMS 内容（{scope}）：{x.title}",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={
                        "path": request.url.path,
                        "method": request.method,
                        "requestId": request.state.request_id,
                        "scope": scope,
                        "beforeStatus": before,
                        "afterStatus": after,
                        "channelId": x.channel_id,
                    },
                )
            )
        await session.commit()

    return ok(data=_content_dto(x), request_id=request.state.request_id)


@router.get("/admin/cms/contents/{id}")
async def admin_get_cms_content_detail(
    request: Request,
    id: str,
    _admin=Depends(require_admin),
):
    """Admin 读侧：内容详情（写侧编辑需要完整字段）。"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        x = (await session.scalars(select(CmsContent).where(CmsContent.id == id).limit(1))).first()
    if x is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "内容不存在"})
    return ok(data=_content_dto(x), request_id=request.state.request_id)
