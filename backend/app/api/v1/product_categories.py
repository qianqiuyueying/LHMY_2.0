"""商品分类接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> E-3 类目与分类体系 -> product-categories 契约
- specs/health-services-platform/tasks.md -> 阶段4-23
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models.enums import CommonEnabledStatus
from app.models.product_category import ProductCategory
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["product-categories"])


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


class ProductCategoryDTO(BaseModel):
    id: str
    name: str
    parentId: str | None = None
    sort: int
    status: str
    createdAt: str
    updatedAt: str


def _dto(c: ProductCategory) -> dict:
    return ProductCategoryDTO(
        id=c.id,
        name=c.name,
        parentId=c.parent_id,
        sort=c.sort,
        status=c.status,
        createdAt=c.created_at.astimezone().isoformat(),
        updatedAt=c.updated_at.astimezone().isoformat(),
    ).model_dump()


@router.get("/product-categories")
async def list_product_categories(request: Request):
    session_factory = get_session_factory()
    async with session_factory() as session:
        items = (
            await session.scalars(
                select(ProductCategory)
                .where(ProductCategory.status == CommonEnabledStatus.ENABLED.value)
                .order_by(ProductCategory.sort.asc(), ProductCategory.created_at.asc())
            )
        ).all()

    return ok(data={"items": [_dto(x) for x in items]}, request_id=request.state.request_id)


@router.get("/admin/product-categories")
async def admin_list_product_categories(request: Request, authorization: str | None = Header(default=None)):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        items = (await session.scalars(select(ProductCategory).order_by(ProductCategory.sort.asc(), ProductCategory.created_at.asc()))).all()

    return ok(data={"items": [_dto(x) for x in items]}, request_id=request.state.request_id)


class AdminCreateProductCategoryBody(BaseModel):
    name: str = Field(..., min_length=1)
    parentId: str | None = None
    sort: int | None = None


@router.post("/admin/product-categories")
async def admin_create_product_category(
    request: Request,
    body: AdminCreateProductCategoryBody,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "name 不能为空"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        c = ProductCategory(
            id=str(uuid4()),
            name=name,
            parent_id=body.parentId,
            sort=int(body.sort or 0),
            status=CommonEnabledStatus.ENABLED.value,
        )
        session.add(c)
        await session.commit()

    return ok(data=_dto(c), request_id=request.state.request_id)


class AdminUpdateProductCategoryBody(BaseModel):
    name: str | None = None
    parentId: str | None = None
    sort: int | None = None
    status: str | None = None


@router.put("/admin/product-categories/{id}")
async def admin_update_product_category(
    request: Request,
    id: str,
    body: AdminUpdateProductCategoryBody,
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
        c = (await session.scalars(select(ProductCategory).where(ProductCategory.id == id).limit(1))).first()
        if c is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "分类不存在"})

        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "name 不能为空"})
            c.name = name
        if body.parentId is not None:
            c.parent_id = body.parentId
        if body.sort is not None:
            c.sort = int(body.sort)
        if body.status is not None:
            c.status = body.status

        await session.commit()

    return ok(data=_dto(c), request_id=request.state.request_id)

