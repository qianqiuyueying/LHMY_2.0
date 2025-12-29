"""服务包模板只读接口（v1 最小可执行）。

规格来源：
- specs/health-services-platform/prototypes/h5.md -> 营销落地页/购买页需要展示：区域级别、等级、服务类别×次数
- specs/health-services-platform/design.md -> 数据模型（service_packages / package_services）
- specs/health-services-platform/tasks.md -> 阶段15（H5 端）+ 属性6（展示格式一致性）

说明：
- design.md 未显式列出该只读接口，但 H5 原型需要展示服务包“模板信息 + 服务类目×次数”，
  因此在 v1 以最小只读接口形式补齐，不引入额外业务能力（仅查询）。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.models.package_service import PackageService
from app.models.service_package import ServicePackage
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["service-packages"])


class ServicePackageServiceItem(BaseModel):
    serviceType: str
    totalCount: int


class ServicePackageDetailResp(BaseModel):
    id: str
    name: str
    regionLevel: str
    tier: str
    description: str | None = None
    services: list[ServicePackageServiceItem]


@router.get("/service-packages/{id}")
async def get_service_package_detail(request: Request, id: str):
    session_factory = get_session_factory()
    async with session_factory() as session:
        sp = (await session.scalars(select(ServicePackage).where(ServicePackage.id == id).limit(1))).first()
        if sp is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "服务包模板不存在"})

        services = (
            await session.scalars(select(PackageService).where(PackageService.service_package_id == sp.id))
        ).all()

    return ok(
        data=ServicePackageDetailResp(
            id=sp.id,
            name=sp.name,
            regionLevel=sp.region_level,
            tier=sp.tier,
            description=sp.description,
            services=[
                ServicePackageServiceItem(serviceType=x.service_type, totalCount=int(x.total_count)) for x in services
            ],
        ).model_dump(),
        request_id=request.state.request_id,
    )
