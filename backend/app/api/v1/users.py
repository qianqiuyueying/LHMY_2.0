"""用户信息（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> `GET /api/v1/users/profile` 契约
- specs/health-services-platform/design.md -> 错误码：UNAUTHENTICATED
- specs/health-services-platform/tasks.md -> 阶段3-20
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.models.user import User
from app.services.user_identity_service import compute_identities_and_member_valid_until
from app.utils.db import get_session_factory
from app.utils.jwt_token import decode_and_validate_user_token
from app.utils.response import ok
from app.utils.auth_header import extract_bearer_token as _extract_bearer_token

router = APIRouter(tags=["users"])

class UserProfileResp(BaseModel):
    id: str
    unionid: str | None = None
    phone: str | None = None
    nickname: str | None = None
    avatar: str | None = None
    identities: list[Literal["MEMBER", "EMPLOYEE"]]
    enterpriseId: str | None = None
    enterpriseName: str | None = None
    memberValidUntil: str | None = None


@router.get("/users/profile")
async def get_profile(request: Request, authorization: str | None = Header(default=None)):
    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token)
    user_id = str(payload.get("sub"))

    session_factory = get_session_factory()
    async with session_factory() as session:
        user = (await session.scalars(select(User).where(User.id == user_id).limit(1))).first()
        if user is None:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})

        identities, member_valid_until = await compute_identities_and_member_valid_until(session=session, user=user)
        user.identities = identities
        await session.commit()

    return ok(
        data=UserProfileResp(
            id=user.id,
            unionid=user.unionid,
            phone=user.phone,
            nickname=user.nickname or None,
            avatar=user.avatar,
            identities=identities,  # type: ignore[arg-type]
            enterpriseId=user.enterprise_id,
            enterpriseName=user.enterprise_name,
            memberValidUntil=member_valid_until.astimezone().isoformat() if member_valid_until else None,
        ).model_dump(),
        request_id=request.state.request_id,
    )


class UpdateUserProfileBody(BaseModel):
    nickname: str | None = None
    avatar: str | None = None


@router.put("/users/profile")
async def update_profile(request: Request, body: UpdateUserProfileBody, authorization: str | None = Header(default=None)):
    """更新用户基础信息（vNow：用于小程序同步微信头像昵称）。"""

    token = _extract_bearer_token(authorization)
    payload = decode_and_validate_user_token(token=token)
    user_id = str(payload.get("sub"))

    nickname = (str(body.nickname or "")).strip()
    avatar = (str(body.avatar or "")).strip()

    if nickname and len(nickname) > 64:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "nickname 过长"})
    if avatar and len(avatar) > 512:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "avatar 过长"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        user = (await session.scalars(select(User).where(User.id == user_id).limit(1))).first()
        if user is None:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})

        if body.nickname is not None:
            user.nickname = nickname
        if body.avatar is not None:
            user.avatar = avatar or None
        await session.commit()

        identities, member_valid_until = await compute_identities_and_member_valid_until(session=session, user=user)

    return ok(
        data=UserProfileResp(
            id=user.id,
            unionid=user.unionid,
            phone=user.phone,
            nickname=user.nickname or None,
            avatar=user.avatar,
            identities=identities,  # type: ignore[arg-type]
            enterpriseId=user.enterprise_id,
            enterpriseName=user.enterprise_name,
            memberValidUntil=member_valid_until.astimezone().isoformat() if member_valid_until else None,
        ).model_dump(),
        request_id=request.state.request_id,
    )
