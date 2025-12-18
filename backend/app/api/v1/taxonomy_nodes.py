"""分类体系接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> E-3 类目与分类体系 -> taxonomy-nodes 契约
- specs/health-services-platform/tasks.md -> 阶段4-23
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.enums import CommonEnabledStatus, TaxonomyType
from app.models.taxonomy_node import TaxonomyNode
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["taxonomy-nodes"])


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


class TaxonomyNodeDTO(BaseModel):
    id: str
    type: str
    name: str
    parentId: str | None = None
    sort: int
    status: str
    createdAt: str
    updatedAt: str


def _dto(n: TaxonomyNode) -> dict:
    return TaxonomyNodeDTO(
        id=n.id,
        type=n.type,
        name=n.name,
        parentId=n.parent_id,
        sort=n.sort,
        status=n.status,
        createdAt=n.created_at.astimezone().isoformat(),
        updatedAt=n.updated_at.astimezone().isoformat(),
    ).model_dump()


@router.get("/mini-program/taxonomy-nodes")
async def list_mini_program_taxonomy_nodes(
    request: Request,
    type: Literal["VENUE", "PRODUCT", "CONTENT"],
):
    session_factory = get_session_factory()
    async with session_factory() as session:
        items = (
            await session.scalars(
                select(TaxonomyNode)
                .where(
                    TaxonomyNode.type == type,
                    TaxonomyNode.status == CommonEnabledStatus.ENABLED.value,
                )
                .order_by(TaxonomyNode.sort.asc(), TaxonomyNode.created_at.asc())
            )
        ).all()

    return ok(data={"items": [_dto(x) for x in items]}, request_id=request.state.request_id)


@router.get("/admin/taxonomy-nodes")
async def admin_list_taxonomy_nodes(
    request: Request,
    authorization: str | None = Header(default=None),
    type: Literal["VENUE", "PRODUCT", "CONTENT"] | None = None,
):
    await _require_admin(authorization)

    stmt = select(TaxonomyNode)
    if type:
        stmt = stmt.where(TaxonomyNode.type == type)
    stmt = stmt.order_by(TaxonomyNode.sort.asc(), TaxonomyNode.created_at.asc())

    session_factory = get_session_factory()
    async with session_factory() as session:
        items = (await session.scalars(stmt)).all()

    return ok(data={"items": [_dto(x) for x in items]}, request_id=request.state.request_id)


class AdminCreateTaxonomyNodeBody(BaseModel):
    type: Literal["VENUE", "PRODUCT", "CONTENT"] = Field(..., description="节点类型")
    name: str = Field(..., min_length=1)
    parentId: str | None = None
    sort: int | None = None


@router.post("/admin/taxonomy-nodes")
async def admin_create_taxonomy_node(
    request: Request,
    body: AdminCreateTaxonomyNodeBody,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "name 不能为空"})

    # 类型校验：对齐枚举，避免写入非法值
    if body.type not in (TaxonomyType.VENUE.value, TaxonomyType.PRODUCT.value, TaxonomyType.CONTENT.value):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "type 不合法"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        n = TaxonomyNode(
            id=str(uuid4()),
            type=body.type,
            name=name,
            parent_id=body.parentId,
            sort=int(body.sort or 0),
            status=CommonEnabledStatus.ENABLED.value,
        )
        session.add(n)
        await session.commit()

    return ok(data=_dto(n), request_id=request.state.request_id)


class AdminUpdateTaxonomyNodeBody(BaseModel):
    name: str | None = None
    parentId: str | None = None
    sort: int | None = None
    status: str | None = None


@router.put("/admin/taxonomy-nodes/{id}")
async def admin_update_taxonomy_node(
    request: Request,
    id: str,
    body: AdminUpdateTaxonomyNodeBody,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    if body.status is not None and body.status not in (
        CommonEnabledStatus.ENABLED.value,
        CommonEnabledStatus.DISABLED.value,
    ):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        n = (await session.scalars(select(TaxonomyNode).where(TaxonomyNode.id == id).limit(1))).first()
        if n is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "节点不存在"})

        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "name 不能为空"})
            n.name = name
        if body.parentId is not None:
            n.parent_id = body.parentId
        if body.sort is not None:
            n.sort = int(body.sort)
        if body.status is not None:
            n.status = body.status

        await session.commit()

    return ok(data=_dto(n), request_id=request.state.request_id)

