"""小程序：卡绑定（bind_token -> BOUND，v1）。

规格来源：
- specs/lhmy-2.0-maintenance/h5-anonymous-purchase-bind-token-v1.md
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.models.bind_token import BindToken
from app.models.card import Card
from app.models.entitlement import Entitlement
from app.models.enums import CardStatus
from app.models.service_package_instance import ServicePackageInstance
from app.utils.db import get_session_factory
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.response import ok
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["mini-program-cards"])


class BindCardByTokenBody(BaseModel):
    token: str = Field(..., min_length=1, max_length=128, description="绑定凭证 bind_token")


class BindCardByTokenResp(BaseModel):
    cardId: str
    status: str  # UNBOUND/BOUND
    alreadyBound: bool = False


@router.post("/mini-program/cards/bind-by-token")
async def mini_program_bind_card_by_token(
    request: Request,
    body: BindCardByTokenBody,
    authorization: str | None = Header(default=None),
):
    # 必须是小程序 token
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token, require_channel="MINI_PROGRAM")
    current_user_id = str(payload["sub"])

    raw = str(body.token or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "token 必填"})

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        bt = (await session.scalars(select(BindToken).where(BindToken.token == raw).limit(1))).first()
        if bt is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "绑定凭证不存在"})

        # 过期/失效
        if bt.expires_at and bt.expires_at <= now:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "绑定凭证已过期"})

        c = (await session.scalars(select(Card).where(Card.id == bt.card_id).limit(1))).first()
        if c is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "卡不存在"})

        # 幂等：已绑定（同一用户）-> 200 no-op；他人 -> 409
        if str(c.status) == CardStatus.BOUND.value:
            if str(c.owner_user_id or "") == current_user_id:
                return ok(
                    data=BindCardByTokenResp(cardId=c.id, status=CardStatus.BOUND.value, alreadyBound=True).model_dump(),
                    request_id=request.state.request_id,
                )
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "卡已绑定，禁止再次绑定"})

        # token 已被使用/作废（滚动失效）-> 不允许绑定
        if bt.used_at is not None:
            raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "绑定凭证已失效，请刷新后重试"})

        # 仅允许 UNBOUND -> BOUND
        if str(c.status) != CardStatus.UNBOUND.value:
            raise HTTPException(status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": "卡状态不允许绑定"})

        # 绑定：卡归属到用户
        c.status = CardStatus.BOUND.value
        c.owner_user_id = current_user_id

        # token 置为已使用（绑定成功后失效）
        bt.used_at = now

        # 迁移权益归属：owner_id/user_id/current_user_id 从 cardId -> userId
        await session.execute(
            update(Entitlement)
            .where(Entitlement.owner_id == c.id, Entitlement.order_id == c.id)
            .values(owner_id=current_user_id, user_id=current_user_id, current_user_id=current_user_id)
        )
        # 迁移服务包实例归属：owner_id 从 cardId -> userId
        await session.execute(
            update(ServicePackageInstance)
            .where(ServicePackageInstance.owner_id == c.id, ServicePackageInstance.order_id == c.id)
            .values(owner_id=current_user_id)
        )

        await session.commit()

    return ok(
        data=BindCardByTokenResp(cardId=c.id, status=CardStatus.BOUND.value, alreadyBound=False).model_dump(),
        request_id=request.state.request_id,
    )


