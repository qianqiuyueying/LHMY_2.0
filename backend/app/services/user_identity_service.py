"""用户身份裁决（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 用户模型 identities 定义（MEMBER/EMPLOYEE 可叠加）
- specs/health-services-platform/design.md -> 企业绑定生效后获得 EMPLOYEE
- specs/health-services-platform/design.md -> MEMBER：由“持有高端服务卡”获得
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ServicePackageInstanceStatus, UserIdentity
from app.models.service_package_instance import ServicePackageInstance
from app.models.user import User


async def compute_identities_and_member_valid_until(
    *,
    session: AsyncSession,
    user: User,
) -> tuple[list[str], datetime | None]:
    identities: list[str] = []

    # EMPLOYEE：企业绑定审核通过后生效（v1：通过后会写入 users.enterprise_id）
    if user.enterprise_id:
        identities.append(UserIdentity.EMPLOYEE.value)

    # MEMBER：持有 ACTIVE 且未过期的高端服务卡实例即可视为会员（取最大有效期做展示）
    now = datetime.now(tz=UTC)
    stmt = (
        select(ServicePackageInstance.valid_until)
        .where(
            ServicePackageInstance.owner_id == user.id,
            ServicePackageInstance.status == ServicePackageInstanceStatus.ACTIVE.value,
            ServicePackageInstance.valid_until > now,
        )
        .order_by(ServicePackageInstance.valid_until.desc())
        .limit(1)
    )
    member_valid_until = await session.scalar(stmt)
    if member_valid_until is not None:
        identities.append(UserIdentity.MEMBER.value)

    # 规格口径：身份数组可叠加；顺序不作为对外契约，但保持稳定输出有利于联调
    identities = sorted(set(identities))
    return identities, member_valid_until
