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

router = APIRouter(tags=["users"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return parts[1].strip()


class UserProfileResp(BaseModel):
    id: str
    unionid: str | None = None
    phone: str | None = None
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
            identities=identities,  # type: ignore[arg-type]
            enterpriseId=user.enterprise_id,
            enterpriseName=user.enterprise_name,
            memberValidUntil=member_valid_until.astimezone().isoformat() if member_valid_until else None,
        ).model_dump(),
        request_id=request.state.request_id,
    )

