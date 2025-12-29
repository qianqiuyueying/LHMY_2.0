"""购物车 API（REQ-P1-001）。

规格来源：
- specs/health-services-platform/后端升级需求与变更清单（v1）.md -> REQ-P1-001

v1 约定（实现口径）：
- 每个用户一辆“当前购物车”（Cart.user_id 唯一）
- add 行为为“存在则累加 quantity”（基于 cart_id+item_type+item_id 唯一）
- 幂等：对 add/update 使用 Idempotency-Key；重复请求返回首次结果
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.models.cart import Cart, CartItem
from app.services.idempotency import IdempotencyCachedResult, IdempotencyService
from app.utils.db import get_session_factory
from app.api.v1.deps import require_user
from app.utils.redis_client import get_redis
from app.utils.response import fail, ok
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["cart"])

def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return idempotency_key.strip()


def _cart_item_dto(x: CartItem) -> dict:
    return {"id": x.id, "itemType": x.item_type, "itemId": x.item_id, "quantity": int(x.quantity)}


async def _idempotency_replay_if_exists(
    *,
    request: Request,
    operation: str,
    actor_id: str,
    idempotency_key: str,
) -> JSONResponse | None:
    idem = IdempotencyService(get_redis())
    cached = await idem.get(operation=operation, actor_type="USER", actor_id=actor_id, idempotency_key=idempotency_key)
    if cached is None:
        return None

    if cached.success:
        payload = ok(data=cached.data, request_id=request.state.request_id)
    else:
        err = cached.error or {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "details": None}
        payload = fail(
            code=str(err.get("code", "INTERNAL_ERROR")),
            message=str(err.get("message", "服务器内部错误")),
            details=err.get("details"),
            request_id=request.state.request_id,
        )

    return JSONResponse(status_code=int(cached.status_code), content=payload)


async def _get_or_create_cart(*, session, user_id: str) -> Cart:
    c = (await session.scalars(select(Cart).where(Cart.user_id == user_id).limit(1))).first()
    if c is not None:
        return c
    c = Cart(id=str(uuid4()), user_id=user_id)
    session.add(c)
    await session.flush()
    return c


@router.get("/cart")
async def get_cart(request: Request, user=Depends(require_user)):
    user_id = str(user.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        c = (await session.scalars(select(Cart).where(Cart.user_id == user_id).limit(1))).first()
        if c is None:
            return ok(data={"items": []}, request_id=request.state.request_id)
        items = (await session.scalars(select(CartItem).where(CartItem.cart_id == c.id))).all()
    return ok(data={"items": [_cart_item_dto(x) for x in items]}, request_id=request.state.request_id)


class AddCartItemBody(BaseModel):
    itemType: str = Field(..., min_length=1)
    itemId: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1, le=9999)


@router.post("/cart/items")
async def add_cart_item(
    request: Request,
    body: AddCartItemBody,
    user=Depends(require_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    user_id = str(user.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="cart_add_item",
        actor_id=user_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    item_type = body.itemType.strip()
    item_id = body.itemId.strip()
    if not item_type or not item_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "itemType/itemId 不能为空"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        c = await _get_or_create_cart(session=session, user_id=user_id)
        existing = (
            await session.scalars(
                select(CartItem)
                .where(CartItem.cart_id == c.id, CartItem.item_type == item_type, CartItem.item_id == item_id)
                .limit(1)
            )
        ).first()
        if existing is None:
            existing = CartItem(id=str(uuid4()), cart_id=c.id, item_type=item_type, item_id=item_id, quantity=int(body.quantity))
            session.add(existing)
        else:
            existing.quantity = int(existing.quantity) + int(body.quantity)
            existing.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(existing)

    data = _cart_item_dto(existing)
    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="cart_add_item",
        actor_type="USER",
        actor_id=user_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return ok(data=data, request_id=request.state.request_id)


class UpdateCartItemBody(BaseModel):
    quantity: int = Field(..., ge=1, le=9999)


@router.put("/cart/items/{id}")
async def update_cart_item(
    request: Request,
    id: str,
    body: UpdateCartItemBody,
    user=Depends(require_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    user_id = str(user.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation="cart_update_item",
        actor_id=user_id,
        idempotency_key=f"{id}:{idem_key}",
    )
    if replay is not None:
        return replay

    session_factory = get_session_factory()
    async with session_factory() as session:
        c = (await session.scalars(select(Cart).where(Cart.user_id == user_id).limit(1))).first()
        if c is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "购物车不存在"})
        x = (await session.scalars(select(CartItem).where(CartItem.id == id, CartItem.cart_id == c.id).limit(1))).first()
        if x is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "购物车项不存在"})
        x.quantity = int(body.quantity)
        x.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(x)

    data = _cart_item_dto(x)
    idem = IdempotencyService(get_redis())
    await idem.set(
        operation="cart_update_item",
        actor_type="USER",
        actor_id=user_id,
        idempotency_key=f"{id}:{idem_key}",
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return ok(data=data, request_id=request.state.request_id)


@router.delete("/cart/items/{id}")
async def delete_cart_item(request: Request, id: str, user=Depends(require_user)):
    user_id = str(user.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        c = (await session.scalars(select(Cart).where(Cart.user_id == user_id).limit(1))).first()
        if c is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "购物车不存在"})
        x = (await session.scalars(select(CartItem).where(CartItem.id == id, CartItem.cart_id == c.id).limit(1))).first()
        if x is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "购物车项不存在"})
        await session.delete(x)
        await session.commit()
    return ok(data={"success": True}, request_id=request.state.request_id)


@router.delete("/cart/items")
async def clear_cart_items(request: Request, user=Depends(require_user)):
    user_id = str(user.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        c = (await session.scalars(select(Cart).where(Cart.user_id == user_id).limit(1))).first()
        if c is None:
            return ok(data={"success": True}, request_id=request.state.request_id)
        await session.execute(delete(CartItem).where(CartItem.cart_id == c.id))
        await session.commit()
    return ok(data={"success": True}, request_id=request.state.request_id)

