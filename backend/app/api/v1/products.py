"""商品接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> B. C 端核心：`GET /api/v1/products` / `GET /api/v1/products/{id}`
- specs/health-services-platform/design.md -> 属性 12：价格优先级计算一致性（price 字段结构）
- specs/health-services-platform/tasks.md -> 阶段4-22
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.models.enums import ProductFulfillmentType, ProductStatus
from app.models.product import Product
from app.models.provider import Provider
from app.utils.db import get_session_factory
from app.utils.jwt_admin_token import decode_and_validate_admin_token, token_blacklist_key
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["products"])


class ProductPrice(BaseModel):
    original: float
    employee: float | None = None
    member: float | None = None
    activity: float | None = None


class ProductListItem(BaseModel):
    id: str
    title: str
    fulfillmentType: Literal["VIRTUAL_VOUCHER", "SERVICE"]
    coverImageUrl: str | None = None
    price: ProductPrice
    tags: list[str] | None = None


class ProductListResp(BaseModel):
    items: list[ProductListItem]
    page: int
    pageSize: int
    total: int


@router.get("/products")
async def list_products(
    request: Request,
    keyword: str | None = None,
    categoryId: str | None = None,
    providerId: str | None = None,
    fulfillmentType: Literal["VIRTUAL_VOUCHER", "SERVICE"] | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    # 分页约束（design.md：默认 20，最大 100）
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Product).where(
        Product.status == ProductStatus.ON_SALE.value,
        Product.fulfillment_type.in_(
            [ProductFulfillmentType.VIRTUAL_VOUCHER.value, ProductFulfillmentType.SERVICE.value]
        ),
    )

    if keyword:
        k = keyword.strip()
        if k:
            stmt = stmt.where(Product.title.like(f"%{k}%"))

    if categoryId:
        stmt = stmt.where(Product.category_id == categoryId)

    if providerId:
        stmt = stmt.where(Product.provider_id == providerId)

    if fulfillmentType:
        stmt = stmt.where(Product.fulfillment_type == fulfillmentType)

    # v1 固定排序：最新创建在前
    stmt = stmt.order_by(Product.created_at.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (
            await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))
        ).all()

    items = [
        ProductListItem(
            id=p.id,
            title=p.title,
            fulfillmentType=p.fulfillment_type,  # type: ignore[arg-type]
            coverImageUrl=p.cover_image_url,
            price=ProductPrice(**(p.price or {})),
            tags=p.tags,
        )
        for p in rows
    ]

    return ok(
        data=ProductListResp(items=items, page=page, pageSize=page_size, total=total).model_dump(),
        request_id=request.state.request_id,
    )


class ProductDetailProvider(BaseModel):
    id: str
    name: str


class ProductDetailResp(BaseModel):
    id: str
    title: str
    fulfillmentType: Literal["VIRTUAL_VOUCHER", "SERVICE"]
    imageUrls: list[str]
    description: str | None = None
    price: ProductPrice
    tags: list[str] | None = None
    provider: ProductDetailProvider


@router.get("/products/{id}")
async def get_product_detail(request: Request, id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (
            await session.scalars(
                select(Product)
                .where(Product.id == id, Product.status == ProductStatus.ON_SALE.value)
                .limit(1)
            )
        ).first()
        pr = None
        if p is not None:
            pr = (await session.scalars(select(Provider).where(Provider.id == p.provider_id).limit(1))).first()

    if p is None:
        # v1 口径：非 ON_SALE 统一按 NOT_FOUND
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "商品不存在"})

    image_urls = p.image_urls or []
    if p.cover_image_url and p.cover_image_url not in image_urls:
        # v1：若只配置了封面图，保证至少有 1 张图片可展示
        image_urls = [p.cover_image_url] + image_urls

    provider = ProductDetailProvider(id=p.provider_id, name=pr.name if pr else "")

    return ok(
        data=ProductDetailResp(
            id=p.id,
            title=p.title,
            fulfillmentType=p.fulfillment_type,  # type: ignore[arg-type]
            imageUrls=image_urls,
            description=p.description,
            price=ProductPrice(**(p.price or {})),
            tags=p.tags,
            provider=provider,
        ).model_dump(),
        request_id=request.state.request_id,
    )


# -----------------------------
# Admin：商品审核与监管（阶段10）
# -----------------------------


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


def _admin_product_list_item(p: Product, provider_name: str | None) -> dict:
    price = p.price or {}
    return {
        "id": p.id,
        "title": p.title,
        "fulfillmentType": p.fulfillment_type,
        "providerId": p.provider_id,
        "providerName": provider_name or "",
        "categoryId": p.category_id,
        "price": {
            "original": float(price.get("original", 0.0)),
            "employee": (float(price["employee"]) if price.get("employee") is not None else None),
            "member": (float(price["member"]) if price.get("member") is not None else None),
            "activity": (float(price["activity"]) if price.get("activity") is not None else None),
        },
        "status": p.status,
        "createdAt": p.created_at.astimezone().isoformat(),
        "updatedAt": p.updated_at.astimezone().isoformat(),
    }


@router.get("/admin/products")
async def admin_list_products(
    request: Request,
    authorization: str | None = Header(default=None),
    keyword: str | None = None,
    providerId: str | None = None,
    categoryId: str | None = None,
    status: Literal["PENDING_REVIEW", "ON_SALE", "OFF_SHELF", "REJECTED"] | None = None,
    fulfillmentType: Literal["VIRTUAL_VOUCHER", "SERVICE"] | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    await _require_admin(authorization)

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Product)

    if keyword and keyword.strip():
        stmt = stmt.where(Product.title.like(f"%{keyword.strip()}%"))
    if providerId and providerId.strip():
        stmt = stmt.where(Product.provider_id == providerId.strip())
    if categoryId and categoryId.strip():
        stmt = stmt.where(Product.category_id == categoryId.strip())
    if status:
        stmt = stmt.where(Product.status == str(status))
    if fulfillmentType:
        stmt = stmt.where(Product.fulfillment_type == str(fulfillmentType))

    stmt = stmt.order_by(Product.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        products = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

        provider_ids = list({p.provider_id for p in products if p.provider_id})
        providers = (
            (await session.scalars(select(Provider).where(Provider.id.in_(provider_ids))))
            .all()
            if provider_ids
            else []
        )
        provider_name_map = {x.id: x.name for x in providers}

    items = [_admin_product_list_item(p, provider_name_map.get(p.provider_id)) for p in products]
    return ok(data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id)


@router.put("/admin/products/{id}/approve")
async def admin_approve_product(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (await session.scalars(select(Product).where(Product.id == id).limit(1))).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "商品不存在"})

        # 状态机：PENDING_REVIEW -> ON_SALE
        if p.status != ProductStatus.PENDING_REVIEW.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "商品状态不允许审核通过"})

        p.status = ProductStatus.ON_SALE.value
        await session.commit()
        await session.refresh(p)

        pr = (await session.scalars(select(Provider).where(Provider.id == p.provider_id).limit(1))).first()

    return ok(data=_admin_product_list_item(p, pr.name if pr else None), request_id=request.state.request_id)


@router.put("/admin/products/{id}/reject")
async def admin_reject_product(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (await session.scalars(select(Product).where(Product.id == id).limit(1))).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "商品不存在"})

        # 状态机：PENDING_REVIEW -> REJECTED
        if p.status != ProductStatus.PENDING_REVIEW.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "商品状态不允许驳回"})

        p.status = ProductStatus.REJECTED.value
        await session.commit()
        await session.refresh(p)

        pr = (await session.scalars(select(Provider).where(Provider.id == p.provider_id).limit(1))).first()

    return ok(data=_admin_product_list_item(p, pr.name if pr else None), request_id=request.state.request_id)


@router.put("/admin/products/{id}/off-shelf")
async def admin_off_shelf_product(
    request: Request,
    id: str,
    authorization: str | None = Header(default=None),
):
    await _require_admin(authorization)

    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (await session.scalars(select(Product).where(Product.id == id).limit(1))).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "商品不存在"})

        # 状态机：ON_SALE -> OFF_SHELF
        if p.status != ProductStatus.ON_SALE.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "商品状态不允许下架"})

        p.status = ProductStatus.OFF_SHELF.value
        await session.commit()
        await session.refresh(p)

        pr = (await session.scalars(select(Provider).where(Provider.id == p.provider_id).limit(1))).first()

    return ok(data=_admin_product_list_item(p, pr.name if pr else None), request_id=request.state.request_id)

