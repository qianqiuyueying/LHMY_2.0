"""标签（全局库）读侧（v1 最小）。

规格来源：
- specs/health-services-platform/tasks.md -> REQ-PROVIDER-P0-003
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.models.enums import CommonEnabledStatus
from app.models.taxonomy_node import TaxonomyNode
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["tags"])


@router.get("/tags")
async def list_tags(request: Request, type: Literal["PRODUCT", "SERVICE", "VENUE"]):
    # 映射到 taxonomy-nodes 的 type（全局标签库）
    t = str(type)
    node_type = {"PRODUCT": "PRODUCT_TAG", "SERVICE": "SERVICE_TAG", "VENUE": "VENUE_TAG"}[t]

    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(TaxonomyNode)
                .where(TaxonomyNode.type == node_type, TaxonomyNode.status == CommonEnabledStatus.ENABLED.value)
                .order_by(TaxonomyNode.sort.asc(), TaxonomyNode.created_at.asc())
            )
        ).all()

    items = [{"id": x.id, "name": x.name, "sort": int(x.sort)} for x in rows]
    return ok(data={"items": items}, request_id=request.state.request_id)


