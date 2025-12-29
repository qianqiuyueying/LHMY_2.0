"""用户收货地址簿（物流商品 v2）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update
from uuid import uuid4

from app.api.v1.deps import require_user
from app.models.user_address import UserAddress
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["user-addresses"])


class AddressDTO(BaseModel):
    id: str
    receiverName: str
    receiverPhone: str
    countryCode: str | None = None
    provinceCode: str | None = None
    cityCode: str | None = None
    districtCode: str | None = None
    addressLine: str
    postalCode: str | None = None
    isDefault: bool


def _dto(a: UserAddress) -> dict:
    return AddressDTO(
        id=a.id,
        receiverName=a.receiver_name,
        receiverPhone=a.receiver_phone,
        countryCode=a.country_code,
        provinceCode=a.province_code,
        cityCode=a.city_code,
        districtCode=a.district_code,
        addressLine=a.address_line,
        postalCode=a.postal_code,
        isDefault=bool(a.is_default),
    ).model_dump()


class UpsertAddressBody(BaseModel):
    receiverName: str = Field(..., min_length=1, max_length=64)
    receiverPhone: str = Field(..., min_length=6, max_length=32)
    countryCode: str | None = None
    provinceCode: str | None = None
    cityCode: str | None = None
    districtCode: str | None = None
    addressLine: str = Field(..., min_length=1, max_length=256)
    postalCode: str | None = Field(default=None, max_length=16)
    isDefault: bool = False

    @model_validator(mode="after")
    def _strip(self):
        self.receiverName = str(self.receiverName or "").strip()
        self.receiverPhone = str(self.receiverPhone or "").strip()
        self.addressLine = str(self.addressLine or "").strip()
        self.countryCode = str(self.countryCode or "").strip() or None
        self.provinceCode = str(self.provinceCode or "").strip() or None
        self.cityCode = str(self.cityCode or "").strip() or None
        self.districtCode = str(self.districtCode or "").strip() or None
        self.postalCode = str(self.postalCode or "").strip() or None
        if not self.receiverName:
            raise ValueError("receiverName 不能为空")
        if not self.receiverPhone:
            raise ValueError("receiverPhone 不能为空")
        if not self.addressLine:
            raise ValueError("addressLine 不能为空")
        return self


@router.get("/user/addresses")
async def list_user_addresses(request: Request, user=Depends(require_user)):
    user_id = str(user.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(UserAddress)
                .where(UserAddress.user_id == user_id)
                .order_by(UserAddress.is_default.desc(), UserAddress.updated_at.desc())
            )
        ).all()
    return ok(data={"items": [_dto(x) for x in rows], "total": len(rows)}, request_id=request.state.request_id)


@router.post("/user/addresses")
async def create_user_address(request: Request, body: UpsertAddressBody, user=Depends(require_user)):
    user_id = str(user.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        if body.isDefault:
            await session.execute(update(UserAddress).where(UserAddress.user_id == user_id).values(is_default=False))

        a = UserAddress(
            id=str(uuid4()),
            user_id=user_id,
            receiver_name=body.receiverName,
            receiver_phone=body.receiverPhone,
            country_code=body.countryCode,
            province_code=body.provinceCode,
            city_code=body.cityCode,
            district_code=body.districtCode,
            address_line=body.addressLine,
            postal_code=body.postalCode,
            is_default=bool(body.isDefault),
        )
        session.add(a)
        await session.commit()
        await session.refresh(a)
    return ok(data=_dto(a), request_id=request.state.request_id)


@router.put("/user/addresses/{id}")
async def update_user_address(request: Request, id: str, body: UpsertAddressBody, user=Depends(require_user)):
    user_id = str(user.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        a = (
            await session.scalars(select(UserAddress).where(UserAddress.id == id, UserAddress.user_id == user_id).limit(1))
        ).first()
        if a is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "地址不存在"})

        if body.isDefault:
            await session.execute(update(UserAddress).where(UserAddress.user_id == user_id).values(is_default=False))

        a.receiver_name = body.receiverName
        a.receiver_phone = body.receiverPhone
        a.country_code = body.countryCode
        a.province_code = body.provinceCode
        a.city_code = body.cityCode
        a.district_code = body.districtCode
        a.address_line = body.addressLine
        a.postal_code = body.postalCode
        a.is_default = bool(body.isDefault)
        await session.commit()
        await session.refresh(a)
    return ok(data=_dto(a), request_id=request.state.request_id)


@router.post("/user/addresses/{id}/set-default")
async def set_default_user_address(request: Request, id: str, user=Depends(require_user)):
    user_id = str(user.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        a = (
            await session.scalars(select(UserAddress).where(UserAddress.id == id, UserAddress.user_id == user_id).limit(1))
        ).first()
        if a is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "地址不存在"})
        await session.execute(update(UserAddress).where(UserAddress.user_id == user_id).values(is_default=False))
        a.is_default = True
        await session.commit()
        await session.refresh(a)
    return ok(data={"success": True, "id": a.id}, request_id=request.state.request_id)


@router.delete("/user/addresses/{id}")
async def delete_user_address(request: Request, id: str, user=Depends(require_user)):
    user_id = str(user.sub)
    session_factory = get_session_factory()
    async with session_factory() as session:
        a = (
            await session.scalars(select(UserAddress).where(UserAddress.id == id, UserAddress.user_id == user_id).limit(1))
        ).first()
        if a is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "地址不存在"})
        await session.delete(a)
        await session.commit()
    return ok(data={"success": True}, request_id=request.state.request_id)


