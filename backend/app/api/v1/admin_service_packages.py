"""Admin 服务包模板管理（可运营，v1.1 最小可执行）。

规格来源：
- specs/health-services-platform/prototypes/admin.md -> 健行天下：高端服务卡/服务包模板
- specs/功能实现/admin/tasks.md -> T-H01

范围（v1.1）：
- 支持：列表 / 详情 / 创建 / 编辑
- 约束：若模板已产生任意 ServicePackageInstance，则禁止修改 regionLevel/tier/服务类目×次数（仅允许改 name/description）
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.v1.deps import require_admin, require_admin_phone_bound
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditActorType
from app.models.enums import CommonEnabledStatus
from app.models.package_service import PackageService
from app.models.service_category import ServiceCategory
from app.models.service_package import ServicePackage
from app.models.service_package_instance import ServicePackageInstance
from app.services.idempotency import IdemActorType, IdempotencyCachedResult, IdempotencyService
from app.utils.redis_client import get_redis
from app.utils.db import get_session_factory
from app.utils.response import fail, ok
from app.utils.datetime_iso import iso as _iso

router = APIRouter(tags=["admin-service-packages"])

_OPERATION_CREATE_SERVICE_PACKAGE = "ADMIN_CREATE_SERVICE_PACKAGE"


class ServicePackageServiceIn(BaseModel):
    serviceType: str = Field(..., min_length=1)
    totalCount: int = Field(..., ge=1)


class ServicePackageItemResp(BaseModel):
    id: str
    name: str
    regionLevel: str
    tier: str
    description: str | None = None
    serviceCount: int
    createdAt: str | None = None
    updatedAt: str | None = None


class ServicePackageDetailResp(BaseModel):
    id: str
    name: str
    regionLevel: str
    tier: str
    description: str | None = None
    services: list[ServicePackageServiceIn]
    locked: bool


class PageResp(BaseModel):
    items: list[ServicePackageItemResp]
    page: int
    pageSize: int
    total: int


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not str(idempotency_key).strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return str(idempotency_key).strip()


async def _idempotency_replay_if_exists(
    *,
    request: Request,
    operation: str,
    actor_type: IdemActorType,
    actor_id: str,
    idempotency_key: str,
) -> JSONResponse | None:
    idem = IdempotencyService(get_redis())
    cached = await idem.get(operation=operation, actor_type=actor_type, actor_id=actor_id, idempotency_key=idempotency_key)
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


def _parse_upsert_body(body: Any) -> dict:
    """手动解析并校验，避免 422 漂移；统一返回 400 INVALID_ARGUMENT + 可读 message。"""

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})

    def _req_str(field: str) -> str:
        val = body.get(field)
        if val is None or not isinstance(val, str) or not val.strip():
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field} 不能为空"})
        return val.strip()

    name = _req_str("name")
    region_level = _req_str("regionLevel").upper()
    tier = _req_str("tier")

    desc_raw = body.get("description")
    description: str | None
    if desc_raw is None:
        description = None
    elif isinstance(desc_raw, str):
        description = desc_raw.strip() or None
    else:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "description 必须是 string 或 null"})

    services_raw = body.get("services")
    if not isinstance(services_raw, list) or len(services_raw) == 0:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "services 不能为空"})

    seen: set[str] = set()
    services: list[dict[str, Any]] = []
    for i, it in enumerate(services_raw):
        if not isinstance(it, dict):
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"services[{i}] 必须是对象"})
        st_raw = it.get("serviceType")
        if st_raw is None or not isinstance(st_raw, str) or not st_raw.strip():
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"services[{i}].serviceType 不能为空"}
            )
        st = st_raw.strip().upper()
        if st in seen:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"serviceType 重复：{st}"})
        seen.add(st)

        tc_raw = it.get("totalCount")
        if isinstance(tc_raw, bool) or not isinstance(tc_raw, (int, float)):
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"services[{i}].totalCount 必须是数字"}
            )
        total_count = int(tc_raw)
        if total_count < 1:
            raise HTTPException(
                status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"services[{i}].totalCount 必须 >= 1"}
            )

        services.append({"serviceType": st, "totalCount": total_count})

    return {
        "name": name,
        "regionLevel": region_level,
        "tier": tier,
        "description": description,
        "services": services,
    }


def _service_package_snapshot(*, sp: ServicePackage, services: list[PackageService]) -> dict:
    return {
        "name": str(sp.name),
        "description": (str(sp.description) if sp.description is not None else None),
        "regionLevel": str(sp.region_level),
        "tier": str(sp.tier),
        "services": [
            {"serviceType": str(x.service_type), "totalCount": int(x.total_count)}
            for x in sorted(services, key=lambda x: str(x.service_type))
        ],
    }


async def _is_locked(*, session, template_id: str) -> bool:
    cnt = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ServicePackageInstance)
                .where(ServicePackageInstance.service_package_template_id == template_id)
            )
        ).scalar()
        or 0
    )
    return cnt > 0


async def _assert_service_types_enabled(*, session, service_types: list[str]) -> None:
    """v1 口径：服务包模板的 serviceType 必须来自“服务大类字典”且已启用。"""

    uniq = sorted({str(x or "").strip().upper() for x in service_types if str(x or "").strip()})
    if not uniq:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "services 不能为空"})

    rows = (
        await session.scalars(
            select(ServiceCategory)
            .where(ServiceCategory.code.in_(uniq), ServiceCategory.status == CommonEnabledStatus.ENABLED.value)
            .limit(len(uniq))
        )
    ).all()
    enabled_codes = {str(x.code).strip().upper() for x in rows}
    missing = [x for x in uniq if x not in enabled_codes]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ARGUMENT", "message": f"serviceType 未在服务大类字典中启用：{', '.join(missing)}"},
        )


@router.get("/admin/service-packages")
async def admin_list_service_packages(
    request: Request,
    page: int = 1,
    pageSize: int = 20,
    keyword: str | None = None,
    _: object = Depends(require_admin),
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))
    kw = (keyword or "").strip()

    stmt = select(ServicePackage)
    if kw:
        stmt = stmt.where(ServicePackage.name.like(f"%{kw}%"))
    stmt = stmt.order_by(ServicePackage.updated_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        packages = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

        ids = [x.id for x in packages]
        svc_counts: dict[str, int] = {}
        if ids:
            rows = (
                await session.execute(
                    select(PackageService.service_package_id, func.count())
                    .where(PackageService.service_package_id.in_(ids))
                    .group_by(PackageService.service_package_id)
                )
            ).all()
            svc_counts = {str(k): int(v) for k, v in rows}

    out = PageResp(
        items=[
            ServicePackageItemResp(
                id=x.id,
                name=x.name,
                regionLevel=x.region_level,
                tier=x.tier,
                description=x.description,
                serviceCount=int(svc_counts.get(x.id, 0)),
                createdAt=_iso(getattr(x, "created_at", None)),
                updatedAt=_iso(getattr(x, "updated_at", None)),
            )
            for x in packages
        ],
        page=page,
        pageSize=page_size,
        total=total,
    ).model_dump()

    return ok(data=out, request_id=request.state.request_id)


@router.get("/admin/service-packages/{id}")
async def admin_get_service_package_detail(request: Request, id: str, _: object = Depends(require_admin)):
    session_factory = get_session_factory()
    async with session_factory() as session:
        sp = (await session.scalars(select(ServicePackage).where(ServicePackage.id == id).limit(1))).first()
        if sp is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "服务包模板不存在"})

        services = (
            await session.scalars(select(PackageService).where(PackageService.service_package_id == sp.id))
        ).all()
        locked = await _is_locked(session=session, template_id=sp.id)

    return ok(
        data=ServicePackageDetailResp(
            id=sp.id,
            name=sp.name,
            regionLevel=sp.region_level,
            tier=sp.tier,
            description=sp.description,
            services=[ServicePackageServiceIn(serviceType=x.service_type, totalCount=int(x.total_count)) for x in services],
            locked=locked,
        ).model_dump(),
        request_id=request.state.request_id,
    )


@router.post("/admin/service-packages")
async def admin_create_service_package(
    request: Request,
    body: dict[str, Any] = Body(default_factory=dict),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    admin=Depends(require_admin_phone_bound),
):
    admin_id = str(admin.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation=_OPERATION_CREATE_SERVICE_PACKAGE,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    try:
        parsed = _parse_upsert_body(body)
        services = parsed["services"]

        session_factory = get_session_factory()
        async with session_factory() as session:
            await _assert_service_types_enabled(session=session, service_types=[x["serviceType"] for x in services])

            sp = ServicePackage(
                id=str(uuid4()),
                name=str(parsed["name"]).strip(),
                region_level=str(parsed["regionLevel"]).strip().upper(),
                tier=str(parsed["tier"]).strip(),
                description=(str(parsed["description"]).strip() if parsed["description"] is not None else None),
            )
            session.add(sp)
            await session.flush()

            for it in services:
                session.add(
                    PackageService(
                        id=str(uuid4()),
                        service_package_id=sp.id,
                        service_type=str(it["serviceType"]).strip().upper(),
                        total_count=int(it["totalCount"]),
                    )
                )

            # 业务审计（必做）：创建模板
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.ADMIN.value,
                    actor_id=admin_id,
                    action=AuditAction.CREATE.value,
                    resource_type="SERVICE_PACKAGE_TEMPLATE",
                    resource_id=str(sp.id),
                    summary="ADMIN 创建服务包模板",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={
                        "requestId": request.state.request_id,
                        "templateId": str(sp.id),
                        "name": str(sp.name),
                        "regionLevel": str(sp.region_level),
                        "tier": str(sp.tier),
                        "serviceTypes": [str(x["serviceType"]) for x in services],
                        "serviceCounts": {str(x["serviceType"]): int(x["totalCount"]) for x in services},
                    },
                )
            )

            await session.commit()

        data = {"id": sp.id}
        await IdempotencyService(get_redis()).set(
            operation=_OPERATION_CREATE_SERVICE_PACKAGE,
            actor_type="ADMIN",
            actor_id=admin_id,
            idempotency_key=idem_key,
            result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
        )
        return ok(data=data, request_id=request.state.request_id)
    except HTTPException as exc:
        # 缓存“首个失败结果”，保证幂等键重放语义一致
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"code": "HTTP_EXCEPTION", "message": "请求错误", "details": exc.detail}
        )
        payload = fail(
            code=str(detail.get("code", "HTTP_EXCEPTION")),
            message=str(detail.get("message", "请求错误")),
            details=detail.get("details"),
            request_id=request.state.request_id,
        )
        await IdempotencyService(get_redis()).set(
            operation=_OPERATION_CREATE_SERVICE_PACKAGE,
            actor_type="ADMIN",
            actor_id=admin_id,
            idempotency_key=idem_key,
            result=IdempotencyCachedResult(
                status_code=int(getattr(exc, "status_code", 400)),
                success=False,
                data=None,
                error={
                    "code": payload["error"]["code"],
                    "message": payload["error"]["message"],
                    "details": payload["error"]["details"],
                },
            ),
        )
        return JSONResponse(status_code=int(getattr(exc, "status_code", 400)), content=payload)


@router.put("/admin/service-packages/{id}")
async def admin_update_service_package(
    request: Request,
    id: str,
    body: dict[str, Any] = Body(default_factory=dict),
    admin=Depends(require_admin_phone_bound),
):
    admin_id = str(admin.sub)
    parsed = _parse_upsert_body(body)
    services = parsed["services"]
    req_map = {str(x["serviceType"]).strip().upper(): int(x["totalCount"]) for x in services}

    session_factory = get_session_factory()
    async with session_factory() as session:
        sp = (await session.scalars(select(ServicePackage).where(ServicePackage.id == id).limit(1))).first()
        if sp is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "服务包模板不存在"})

        locked = await _is_locked(session=session, template_id=sp.id)
        new_name = str(parsed["name"]).strip()
        new_desc = str(parsed["description"]).strip() if parsed["description"] is not None else None
        new_region_level = str(parsed["regionLevel"]).strip().upper()
        new_tier = str(parsed["tier"]).strip()

        current_services = (
            await session.scalars(select(PackageService).where(PackageService.service_package_id == sp.id))
        ).all()
        before = _service_package_snapshot(sp=sp, services=current_services)
        cur_map = {str(x.service_type).strip().upper(): int(x.total_count) for x in current_services}

        changed_fields: list[str] = []
        if new_name != str(sp.name):
            changed_fields.append("name")
        if (new_desc or None) != (str(sp.description).strip() if sp.description is not None else None):
            changed_fields.append("description")

        if locked:
            # v1.1 固化：已产生实例后，禁止修改 regionLevel/tier/明细（避免历史口径漂移）
            if new_region_level != str(sp.region_level).strip().upper() or new_tier != str(sp.tier).strip():
                raise HTTPException(
                    status_code=409,
                    detail={"code": "STATE_CONFLICT", "message": "模板已产生实例，禁止修改 regionLevel/tier"},
                )

            # 对明细做“集合等价”校验
            if cur_map != req_map:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "STATE_CONFLICT", "message": "模板已产生实例，禁止修改服务类目×次数"},
                )
        else:
            if new_region_level != str(sp.region_level).strip().upper():
                changed_fields.append("regionLevel")
            if new_tier != str(sp.tier).strip():
                changed_fields.append("tier")
            if cur_map != req_map:
                changed_fields.append("services")
                await _assert_service_types_enabled(session=session, service_types=[x["serviceType"] for x in services])

        # no-op：200 返回，不写审计
        if not changed_fields:
            await session.commit()
            return ok(data={"id": sp.id, "locked": locked}, request_id=request.state.request_id)

        # 可更新字段
        sp.name = new_name
        sp.description = new_desc

        if not locked:
            sp.region_level = new_region_level
            sp.tier = new_tier

            # 重写明细（最小实现：删除旧明细再插入新明细）
            for x in current_services:
                await session.delete(x)
            await session.flush()

            for it in services:
                session.add(
                    PackageService(
                        id=str(uuid4()),
                        service_package_id=sp.id,
                        service_type=str(it["serviceType"]).strip().upper(),
                        total_count=int(it["totalCount"]),
                    )
                )

        after_services = (
            await session.scalars(select(PackageService).where(PackageService.service_package_id == sp.id))
        ).all()
        after = _service_package_snapshot(sp=sp, services=after_services)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.UPDATE.value,
                resource_type="SERVICE_PACKAGE_TEMPLATE",
                resource_id=str(sp.id),
                summary="ADMIN 更新服务包模板",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "templateId": str(sp.id),
                    "locked": bool(locked),
                    "changedFields": changed_fields,
                    "before": before,
                    "after": after,
                },
            )
        )

        await session.commit()

    return ok(data={"id": sp.id, "locked": locked}, request_id=request.state.request_id)

