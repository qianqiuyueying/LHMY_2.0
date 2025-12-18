"""小程序认证（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> A.认证与会话：mini-program/auth/login、mini-program/auth/bind-phone
- specs/health-services-platform/design.md -> 跨端身份联通口径（合并/迁移表清单）
- specs/health-services-platform/tasks.md -> 阶段3-16
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy import update

from app.models.after_sale_case import AfterSaleCase
from app.models.booking import Booking
from app.models.entitlement import Entitlement
from app.models.entitlement_transfer import EntitlementTransfer
from app.models.order import Order
from app.models.redemption_record import RedemptionRecord
from app.models.service_package_instance import ServicePackageInstance
from app.models.user import User
from app.services.sms_code_service import SmsCodeService
from app.services.user_identity_service import compute_identities_and_member_valid_until
from app.services.wechat_code_exchange import exchange_wechat_code
from app.utils.db import get_session_factory
from app.utils.jwt_token import create_user_token, decode_and_validate_user_token
from app.utils.redis_client import get_redis
from app.utils.response import ok

router = APIRouter(tags=["mini-program-auth"])


class MiniProgramLoginBody(BaseModel):
    code: str = Field(..., description="微信登录 code（支持 mock:unionid:xxx / mock:openid:xxx）")


class MiniProgramLoginUser(BaseModel):
    id: str
    openid: str
    unionid: str | None = None
    phone: str | None = None
    identities: list[Literal["MEMBER", "EMPLOYEE"]]


class MiniProgramLoginResp(BaseModel):
    token: str
    user: MiniProgramLoginUser


@router.post("/mini-program/auth/login")
async def mini_program_login(request: Request, body: MiniProgramLoginBody):
    wx = await exchange_wechat_code(code=body.code)

    openid = wx.openid
    unionid = wx.unionid

    session_factory = get_session_factory()
    async with session_factory() as session:
        user: User | None = None
        if unionid:
            user = (await session.scalars(select(User).where(User.unionid == unionid).limit(1))).first()
        if user is None:
            user = (await session.scalars(select(User).where(User.openid == openid).limit(1))).first()

        if user is None:
            user = User(
                id=str(uuid4()),
                phone=None,
                openid=openid,
                unionid=unionid,
                nickname="",
                avatar=None,
                identities=[],
                enterprise_id=None,
                enterprise_name=None,
                binding_time=None,
            )
            session.add(user)
        else:
            # 若之前仅有 openid，后续拿到了 unionid，则补写（有利于跨端联通）
            if unionid and not user.unionid:
                user.unionid = unionid
            # 保持 openid 最新（理论上稳定）
            if not user.openid:
                user.openid = openid

        identities, _member_valid_until = await compute_identities_and_member_valid_until(session=session, user=user)
        user.identities = identities
        await session.commit()

    token = create_user_token(user_id=user.id, channel="MINI_PROGRAM")
    return ok(
        data=MiniProgramLoginResp(
            token=token,
            user=MiniProgramLoginUser(
                id=user.id,
                openid=openid,
                unionid=user.unionid,
                phone=user.phone,
                identities=identities,  # type: ignore[arg-type]
            ),
        ).model_dump(),
        request_id=request.state.request_id,
    )


class MiniProgramBindPhoneBody(BaseModel):
    phone: str
    smsCode: str = Field(..., min_length=4, max_length=10)


class MiniProgramBindPhoneResp(BaseModel):
    token: str
    user: MiniProgramLoginUser


def _conflict(conflict_type: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "ACCOUNT_BIND_CONFLICT",
            "message": "账号合并冲突",
            "details": {"conflictType": conflict_type, "message": message},
        },
    )


@router.post("/mini-program/auth/bind-phone")
async def mini_program_bind_phone(request: Request, body: MiniProgramBindPhoneBody):
    # 1) 防串用校验：必须是小程序 token
    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    token = auth.split(" ", 1)[1].strip()
    payload = decode_and_validate_user_token(token=token, require_channel="MINI_PROGRAM")
    current_user_id = str(payload["sub"])

    # 2) 短信校验（绑定手机号场景）
    sms_service = SmsCodeService(get_redis())
    await sms_service.verify_code(phone=body.phone, scene="MP_BIND_PHONE", sms_code=body.smsCode)

    # 3) 合并逻辑（手机号账户为主账户）
    session_factory = get_session_factory()
    async with session_factory() as session:
        current = (await session.scalars(select(User).where(User.id == current_user_id).limit(1))).first()
        if current is None:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})

        if not current.openid:
            # 小程序登录必定有 openid
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})

        if current.phone and current.phone != body.phone:
            raise _conflict("UNIONID_BOUND_TO_OTHER_PHONE", "当前微信账号已绑定其他手机号")

        phone_user = (await session.scalars(select(User).where(User.phone == body.phone).limit(1))).first()

        # Case A：手机号不存在 -> 直接绑定到当前用户
        if phone_user is None:
            current.phone = body.phone
            identities, _member_valid_until = await compute_identities_and_member_valid_until(session=session, user=current)
            current.identities = identities
            await session.commit()

            new_token = create_user_token(user_id=current.id, channel="MINI_PROGRAM")
            return ok(
                data=MiniProgramBindPhoneResp(
                    token=new_token,
                    user=MiniProgramLoginUser(
                        id=current.id,
                        unionid=current.unionid,
                        phone=current.phone,
                        identities=identities,  # type: ignore[arg-type]
                    ),
                ).model_dump(),
                request_id=request.state.request_id,
            )

        # Case B：手机号已存在 -> 合并到手机号账户（target）
        target = phone_user

        # 已绑定 unionid 的手机号账户不可再绑定其他微信账号（unionid 优先；若无 unionid 则用 openid 判断）
        if target.unionid and current.unionid and target.unionid != current.unionid:
            raise _conflict("PHONE_BOUND_TO_OTHER_UNIONID", "手机号已绑定其他微信账号")
        if target.openid and target.openid != current.openid:
            raise _conflict("PHONE_BOUND_TO_OTHER_UNIONID", "手机号已绑定其他微信账号")

        source_user_id = current.id
        target_user_id = target.id

        # 将 openid/unionid 绑定到主账户，并清理源账户，避免唯一冲突
        target.openid = current.openid
        if current.unionid:
            target.unionid = current.unionid
        target.phone = body.phone
        current.unionid = None
        current.openid = None
        current.phone = None

        # 按规格清单迁移裁决字段（事务内原子更新）
        await session.execute(update(Entitlement).where(Entitlement.owner_id == source_user_id).values(owner_id=target_user_id))
        await session.execute(
            update(ServicePackageInstance)
            .where(ServicePackageInstance.owner_id == source_user_id)
            .values(owner_id=target_user_id)
        )
        await session.execute(update(Order).where(Order.user_id == source_user_id).values(user_id=target_user_id))
        await session.execute(update(Booking).where(Booking.user_id == source_user_id).values(user_id=target_user_id))
        await session.execute(
            update(AfterSaleCase).where(AfterSaleCase.user_id == source_user_id).values(user_id=target_user_id)
        )
        await session.execute(
            update(RedemptionRecord)
            .where(RedemptionRecord.user_id == source_user_id)
            .values(user_id=target_user_id)
        )
        await session.execute(
            update(EntitlementTransfer)
            .where(EntitlementTransfer.from_owner_id == source_user_id)
            .values(from_owner_id=target_user_id)
        )
        await session.execute(
            update(EntitlementTransfer)
            .where(EntitlementTransfer.to_owner_id == source_user_id)
            .values(to_owner_id=target_user_id)
        )

        identities, _member_valid_until = await compute_identities_and_member_valid_until(session=session, user=target)
        target.identities = identities

        try:
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            # 并发下可能触发唯一索引冲突，统一按 409 返回
            raise _conflict("UNIQUE_CONSTRAINT", "账号绑定发生冲突，请稍后重试") from exc

    new_token = create_user_token(user_id=target.id, channel="MINI_PROGRAM")
    return ok(
        data=MiniProgramBindPhoneResp(
            token=new_token,
            user=MiniProgramLoginUser(
                id=target.id,
                openid=target.openid or "",
                unionid=target.unionid,
                phone=target.phone,
                identities=identities,  # type: ignore[arg-type]
            ),
        ).model_dump(),
        request_id=request.state.request_id,
    )

