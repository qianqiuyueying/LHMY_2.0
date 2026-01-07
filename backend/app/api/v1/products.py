"""商品接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> B. C 端核心：`GET /api/v1/products` / `GET /api/v1/products/{id}`
- specs/health-services-platform/design.md -> 属性 12：价格优先级计算一致性（price 字段结构）
- specs/health-services-platform/tasks.md -> 阶段4-22
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from app.models.enums import ProductFulfillmentType, ProductStatus
from app.models.product import Product
from app.models.provider import Provider
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.api.v1.deps import require_admin
from app.services.rbac import ActorContext
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["products"])


class ProductPrice(BaseModel):
    original: float
    employee: float | None = None
    member: float | None = None
    activity: float | None = None


class ProductListItem(BaseModel):
    id: str
    title: str
    fulfillmentType: Literal["SERVICE", "PHYSICAL_GOODS"]
    coverImageUrl: str | None = None
    price: ProductPrice
    tags: list[str] | None = None
    stock: int | None = None
    reservedStock: int | None = None
    weight: float | None = None
    shippingFee: float | None = None


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
    fulfillmentType: Literal["SERVICE", "PHYSICAL_GOODS"] | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    # 分页约束（design.md：默认 20，最大 100）
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    stmt = select(Product).where(
        Product.status == ProductStatus.ON_SALE.value,
        Product.fulfillment_type.in_([ProductFulfillmentType.SERVICE.value, ProductFulfillmentType.PHYSICAL_GOODS.value]),
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
        rows = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items = [
        ProductListItem(
            id=p.id,
            title=p.title,
            fulfillmentType=p.fulfillment_type,  # type: ignore[arg-type]
            coverImageUrl=p.cover_image_url,
            price=ProductPrice(**(p.price or {})),
            tags=p.tags,
            stock=int(p.stock or 0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
            reservedStock=int(p.reserved_stock or 0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
            weight=(float(p.weight) if p.weight is not None else None) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
            shippingFee=float(p.shipping_fee or 0.0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
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
    fulfillmentType: Literal["SERVICE", "PHYSICAL_GOODS"]
    imageUrls: list[str]
    description: str | None = None
    price: ProductPrice
    tags: list[str] | None = None
    provider: ProductDetailProvider
    stock: int | None = None
    reservedStock: int | None = None
    weight: float | None = None
    shippingFee: float | None = None


@router.get("/products/{id}")
async def get_product_detail(request: Request, id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (
            await session.scalars(
                select(Product).where(Product.id == id, Product.status == ProductStatus.ON_SALE.value).limit(1)
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
            stock=int(p.stock or 0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
            reservedStock=int(p.reserved_stock or 0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
            weight=(float(p.weight) if p.weight is not None else None) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
            shippingFee=float(p.shipping_fee or 0.0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
        ).model_dump(),
        request_id=request.state.request_id,
    )


# -----------------------------
# Admin：商品审核与监管（阶段10）
# -----------------------------


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
        "stock": int(p.stock or 0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
        "reservedStock": int(p.reserved_stock or 0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
        "weight": float(p.weight) if (p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value and p.weight is not None) else None,
        "shippingFee": float(p.shipping_fee or 0.0) if p.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value else None,
        "status": p.status,
        "rejectReason": getattr(p, "reject_reason", None),
        "rejectedAt": _iso(getattr(p, "rejected_at", None)),
        "createdAt": _iso(p.created_at),
        "updatedAt": _iso(p.updated_at),
    }


class AdminRejectProductBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200)

    @model_validator(mode="after")
    def _trim(self):
        self.reason = str(self.reason or "").strip()
        if not self.reason:
            raise ValueError("reason 不能为空")
        return self


@router.get("/admin/products")
async def admin_list_products(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    keyword: str | None = None,
    providerId: str | None = None,
    categoryId: str | None = None,
    status: Literal["PENDING_REVIEW", "ON_SALE", "OFF_SHELF", "REJECTED"] | None = None,
    fulfillmentType: Literal["SERVICE", "PHYSICAL_GOODS"] | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

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
            (await session.scalars(select(Provider).where(Provider.id.in_(provider_ids)))).all() if provider_ids else []
        )
        provider_name_map = {x.id: x.name for x in providers}

    items = [_admin_product_list_item(p, provider_name_map.get(p.provider_id)) for p in products]
    return ok(
        data={"items": items, "page": page, "pageSize": page_size, "total": total}, request_id=request.state.request_id
    )


@router.put("/admin/products/{id}/approve")
async def admin_approve_product(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin),
):
    _ = _admin

    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (await session.scalars(select(Product).where(Product.id == id).limit(1))).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "商品不存在"})

        # 状态机：PENDING_REVIEW -> ON_SALE
        if p.status != ProductStatus.PENDING_REVIEW.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "商品状态不允许审核通过"})

        p.status = ProductStatus.ON_SALE.value
        p.reject_reason = None
        p.rejected_at = None
        await session.commit()
        await session.refresh(p)

        pr = (await session.scalars(select(Provider).where(Provider.id == p.provider_id).limit(1))).first()

    return ok(data=_admin_product_list_item(p, pr.name if pr else None), request_id=request.state.request_id)


@router.put("/admin/products/{id}/reject")
async def admin_reject_product(
    request: Request,
    id: str,
    body: AdminRejectProductBody,
    _admin: ActorContext = Depends(require_admin),
):
    _ = _admin

    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (await session.scalars(select(Product).where(Product.id == id).limit(1))).first()
        if p is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "商品不存在"})

        # 状态机：PENDING_REVIEW -> REJECTED
        if p.status != ProductStatus.PENDING_REVIEW.value:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "商品状态不允许驳回"})

        p.status = ProductStatus.REJECTED.value
        p.reject_reason = str(body.reason or "").strip()
        p.rejected_at = datetime.utcnow()
        await session.commit()
        await session.refresh(p)

        pr = (await session.scalars(select(Provider).where(Provider.id == p.provider_id).limit(1))).first()

    return ok(data=_admin_product_list_item(p, pr.name if pr else None), request_id=request.state.request_id)


@router.put("/admin/products/{id}/off-shelf")
async def admin_off_shelf_product(
    request: Request,
    id: str,
    _admin: ActorContext = Depends(require_admin),
):
    _ = _admin

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
