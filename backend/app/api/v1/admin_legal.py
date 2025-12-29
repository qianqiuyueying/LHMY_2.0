"""协议/条款管理（Admin，v1 最小）。

规格来源：
- specs/health-services-platform/tasks.md -> REQ-ADMIN-P0-008
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import bleach
import markdown as mdlib
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.v1.deps import require_admin
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType, LegalAgreementStatus
from app.models.legal_agreement import LegalAgreement
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-legal"])

def _dto(x: LegalAgreement) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "title": x.title,
        "contentHtml": x.content_html,
        "contentMd": getattr(x, "content_md", None),
        "version": x.version,
        "status": x.status,
        "publishedAt": _iso(x.published_at),
        "createdAt": _iso(x.created_at),
        "updatedAt": _iso(x.updated_at),
    }


def _markdown_to_safe_html(raw_md: str) -> str:
    text = str(raw_md or "")
    html = mdlib.markdown(
        text,
        extensions=[
            "extra",
            "sane_lists",
            "toc",
            # 支持删除线语法：~~text~~ -> <del>text</del>
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
    clean = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=["http", "https"],
        strip=True,
    )
    clean = bleach.linkify(clean, callbacks=[bleach.callbacks.nofollow])
    return clean


@router.get("/admin/legal/agreements")
async def admin_list_legal_agreements(
    request: Request,
    _admin=Depends(require_admin),
    keyword: str | None = None,
    status: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(LegalAgreement)
    if status and status.strip():
        stmt = stmt.where(LegalAgreement.status == status.strip())
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(LegalAgreement.code.like(kw) | LegalAgreement.title.like(kw))

    stmt = stmt.order_by(LegalAgreement.updated_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    return ok(
        data={"items": [_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )


@router.get("/admin/legal/agreements/{code}")
async def admin_get_legal_agreement(
    request: Request,
    code: str,
    _admin=Depends(require_admin),
):
    _ = _admin
    code = str(code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "code 不能为空"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(LegalAgreement).where(LegalAgreement.code == code).limit(1))).first()

    if row is None:
        return ok(
            data={"id": "", "code": code, "title": "", "contentHtml": "", "version": "0", "status": "DRAFT", "publishedAt": None},
            request_id=request.state.request_id,
        )
    return ok(data=_dto(row), request_id=request.state.request_id)


class UpsertAgreementBody(BaseModel):
    title: str = Field(default="", max_length=256)
    contentHtml: str = Field(default="")
    contentMd: str | None = None
    version: str | None = Field(default=None, max_length=32)


@router.put("/admin/legal/agreements/{code}")
async def admin_upsert_legal_agreement(
    request: Request,
    code: str,
    body: UpsertAgreementBody,
    admin=Depends(require_admin),
):
    code = str(code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "code 不能为空"})

    title = str(body.title or "").strip()
    content_md = (str(body.contentMd).strip() if body.contentMd is not None else None)
    content_html = str(body.contentHtml or "")
    if content_md is not None:
        if not content_md:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "contentMd 不能为空"})
        content_html = _markdown_to_safe_html(content_md)
    version = str(body.version or str(int(datetime.now(tz=UTC).timestamp())))

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(LegalAgreement).where(LegalAgreement.code == code).limit(1))).first()
        action = AuditAction.UPDATE.value
        if row is None:
            action = AuditAction.CREATE.value
            row = LegalAgreement(
                id=str(uuid4()),
                code=code,
                title=title,
                content_md=content_md,
                content_html=content_html,
                version=version,
                status=LegalAgreementStatus.DRAFT.value,
                published_at=None,
            )
            session.add(row)
        else:
            row.title = title
            row.content_md = content_md
            row.content_html = content_html
            row.version = version
            row.status = LegalAgreementStatus.DRAFT.value

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                # ActorContext：sub 为操作者唯一标识（admin/user/provider/dealer）
                actor_id=str(getattr(admin, "sub", "") or ""),
                action=action,
                resource_type="LEGAL_AGREEMENT",
                resource_id=code,
                summary=f"协议草稿保存：{code}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"code": code, "requestId": request.state.request_id},
            )
        )

        await session.commit()
        await session.refresh(row)

    return ok(data=_dto(row), request_id=request.state.request_id)


@router.post("/admin/legal/agreements/{code}/publish")
async def admin_publish_legal_agreement(request: Request, code: str, admin=Depends(require_admin)):
    code = str(code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "code 不能为空"})

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(LegalAgreement).where(LegalAgreement.code == code).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "协议不存在，请先保存草稿"})
        row.status = LegalAgreementStatus.PUBLISHED.value
        row.published_at = now

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(getattr(admin, "sub", "") or ""),
                action=AuditAction.PUBLISH.value,
                resource_type="LEGAL_AGREEMENT",
                resource_id=code,
                summary=f"协议发布：{code}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"code": code, "requestId": request.state.request_id},
            )
        )
        await session.commit()
        await session.refresh(row)

    return ok(data=_dto(row), request_id=request.state.request_id)


@router.post("/admin/legal/agreements/{code}/offline")
async def admin_offline_legal_agreement(request: Request, code: str, admin=Depends(require_admin)):
    code = str(code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "code 不能为空"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(LegalAgreement).where(LegalAgreement.code == code).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "协议不存在"})
        row.status = LegalAgreementStatus.OFFLINE.value

        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=str(getattr(admin, "sub", "") or ""),
                action=AuditAction.OFFLINE.value,
                resource_type="LEGAL_AGREEMENT",
                resource_id=code,
                summary=f"协议下线：{code}",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"code": code, "requestId": request.state.request_id},
            )
        )
        await session.commit()
        await session.refresh(row)

    return ok(data=_dto(row), request_id=request.state.request_id)


