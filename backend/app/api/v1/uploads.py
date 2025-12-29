"""Uploads（v1：图片上传，落盘 + 静态访问）。

规格来源：
- specs/health-services-platform/provider-venue-profile-v1.md -> 4.1 上传（v1）
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select

from app.api.v1.deps import optional_actor
from app.models.asset import Asset
from app.services.rbac import ActorContext, ActorType, require_actor_types
from app.services.storage import LocalStaticStorage
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.settings import settings

router = APIRouter(tags=["uploads"])

_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpg": "jpg",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


def _static_upload_root() -> Path:
    # backend/app/api/v1/uploads.py -> backend/app/static/uploads
    return Path(__file__).resolve().parents[2] / "static" / "uploads"


@router.post("/uploads/images")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    actor: ActorContext | None = Depends(optional_actor),
):
    if actor is None:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    # vNow：小程序用户头像上传需要 USER 权限
    require_actor_types(actor=actor, allowed={ActorType.ADMIN, ActorType.PROVIDER, ActorType.PROVIDER_STAFF, ActorType.USER})

    content_type = str(getattr(file, "content_type", "") or "").strip().lower()
    ext = _ALLOWED_CONTENT_TYPES.get(content_type)
    if not ext:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "仅支持 png/jpg/jpeg/webp 图片"})

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "文件为空"})
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "图片大小不能超过 5MB"})

    # v2：资产库 + sha256 去重（重复上传返回同一 url，不重复落盘）
    digest = hashlib.sha256(data).hexdigest()

    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = (
            await session.scalars(select(Asset).where(Asset.kind == "IMAGE", Asset.sha256 == digest).limit(1))
        ).first()
        if existing is not None:
            return ok(data={"url": existing.url}, request_id=request.state.request_id)

        # 存储抽象：LOCAL（/static/uploads/...）
        now = datetime.now()
        static_dir = Path(__file__).resolve().parents[2] / "static"
        static_dir.mkdir(parents=True, exist_ok=True)
        stored = LocalStaticStorage(static_dir=static_dir, public_base_url=settings.assets_public_base_url).put_image(
            data=data, ext=ext, now=now
        )

        x = Asset(
            id=str(uuid4()),
            kind="IMAGE",
            sha256=digest,
            size_bytes=len(data),
            mime=content_type,
            ext=ext,
            storage=stored.storage,
            storage_key=stored.storage_key,
            url=stored.url,
            original_filename=str(getattr(file, "filename", "") or "")[:256],
            created_by_actor_type=str(getattr(actor, "actor_type", "") or ""),
            created_by_actor_id=str(getattr(actor, "sub", "") or ""),
        )
        session.add(x)
        await session.commit()

    return ok(data={"url": stored.url}, request_id=request.state.request_id)

