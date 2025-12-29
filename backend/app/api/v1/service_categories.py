"""服务大类（serviceType 字典）读接口（v1）。

规格来源：
- specs/health-services-platform/service-category-management.md
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, or_, select

from app.models.enums import CommonEnabledStatus
from app.models.service_category import ServiceCategory
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso


router = APIRouter(tags=["service-categories"])

def _dto(x: ServiceCategory) -> dict:
    return {
        "id": x.id,
        "code": x.code,
        "displayName": x.display_name,
        "status": x.status,
        "sort": int(x.sort or 0),
        "createdAt": _iso(x.created_at),
        "updatedAt": _iso(x.updated_at),
    }


@router.get("/service-categories")
async def list_enabled_service_categories(
    request: Request,
    keyword: str | None = None,
    page: int = 1,
    pageSize: int = 200,
):
    page = max(1, int(page))
    page_size = max(1, min(500, int(pageSize)))

    stmt = select(ServiceCategory).where(ServiceCategory.status == CommonEnabledStatus.ENABLED.value)
    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        stmt = stmt.where(or_(ServiceCategory.code.like(like), ServiceCategory.display_name.like(like)))

    stmt = stmt.order_by(ServiceCategory.sort.desc(), ServiceCategory.updated_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    # v1：若启用项为 0，返回空列表即可（由各端提示运营先维护字典）
    if page > 1 and not rows:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "page 超出范围"})

    return ok(
        data={"items": [_dto(x) for x in rows], "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )

