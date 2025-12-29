from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select

from app.api.v1.deps import require_admin
from app.models.asset import Asset
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-assets"])


@router.get("/admin/assets")
async def admin_list_assets(
    request: Request,
    _admin=Depends(require_admin),
    kind: Literal["IMAGE"] = "IMAGE",
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Asset).where(Asset.kind == kind)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Asset.original_filename.like(kw), Asset.url.like(kw), Asset.sha256.like(kw)))

    stmt = stmt.order_by(Asset.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        items = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    data_items = [
        {
            "id": x.id,
            "kind": x.kind,
            "url": x.url,
            "sha256": x.sha256,
            "sizeBytes": int(x.size_bytes or 0),
            "mime": x.mime,
            "ext": x.ext,
            "originalFilename": x.original_filename or None,
            "createdAt": _iso(x.created_at),
        }
        for x in items
    ]
    return ok(data={"items": data_items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


