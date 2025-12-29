"""权益生成服务（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 权益模型 / 高端服务卡实例与权益生成规则
- specs/health-services-platform/tasks.md -> 阶段5-28

v1 最小口径（已在 tasks.md 28.1 中确认）：
- validFrom = orders.paidAt
- validUntil = orders.paidAt + 365 days
- voucherCode = uuid4().hex[:16].upper()

说明：
- 该模块实现“支付成功后自动生成权益”的副作用逻辑；
- 幂等口径：同一 orderId 若已生成过 entitlements，则不重复生成。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.models.entitlement import Entitlement
from app.models.enums import EntitlementStatus, EntitlementType, OrderItemType, OrderType
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.package_service import PackageService
from app.models.product import Product
from app.models.service_package_instance import ServicePackageInstance
from app.services.entitlement_qr_signing import build_payload_text, sign_payload
from app.services.entitlement_rules import EntitlementShape, validate_entitlement_shape


def _voucher_code_v1() -> str:
    return uuid4().hex[:16].upper()


def _build_qr_payload_v1(*, secret: str, entitlement_id: str, voucher_code: str, now_ts: int) -> str:
    nonce = uuid4().hex
    sign = sign_payload(secret=secret, entitlement_id=entitlement_id, voucher_code=voucher_code, ts=now_ts, nonce=nonce)
    return build_payload_text(
        entitlement_id=entitlement_id, voucher_code=voucher_code, ts=now_ts, nonce=nonce, sign=sign
    )


def _valid_window_from_paid_at(paid_at: datetime) -> tuple[datetime, datetime]:
    valid_from = paid_at
    valid_until = paid_at + timedelta(days=365)
    return valid_from, valid_until


async def _ensure_not_generated_yet(*, session, order_id: str) -> bool:
    """返回 True 表示已生成过（无需重复生成）。"""

    existing = await session.scalar(select(Entitlement.id).where(Entitlement.order_id == order_id).limit(1))
    return existing is not None


async def generate_entitlements_after_payment_succeeded(*, session, order_id: str, qr_sign_secret: str) -> int:
    """按订单类型生成权益。

    返回：本次生成的 entitlement 数量（幂等重复调用返回 0）。
    """

    o: Order | None = (await session.scalars(select(Order).where(Order.id == order_id).limit(1))).first()
    if o is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})

    if o.paid_at is None:
        raise HTTPException(
            status_code=409, detail={"code": "STATE_CONFLICT", "message": "订单未支付成功，无法生成权益"}
        )

    if await _ensure_not_generated_yet(session=session, order_id=o.id):
        return 0

    try:
        order_type = OrderType(o.order_type)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "orderType 不合法"}
        ) from exc

    items: list[OrderItem] = (await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all()
    if not items:
        return 0

    now_ts = int(datetime.now(tz=UTC).timestamp())
    valid_from, valid_until = _valid_window_from_paid_at(o.paid_at)

    created = 0
    if order_type == OrderType.SERVICE_PACKAGE:
        for it in items:
            if it.item_type != OrderItemType.SERVICE_PACKAGE.value:
                continue
            if not it.service_package_template_id or not it.region_scope or not it.tier:
                raise HTTPException(
                    status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "服务包明细缺少必要参数"}
                )

            # 拉取模板的“服务类目×次数”
            ps_list: list[PackageService] = (
                await session.scalars(
                    select(PackageService).where(PackageService.service_package_id == it.service_package_template_id)
                )
            ).all()
            if not ps_list:
                raise HTTPException(
                    status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "服务包模板未配置服务类别×次数"}
                )

            for _ in range(int(it.quantity)):
                sp_id = str(uuid4())
                sp = ServicePackageInstance(
                    id=sp_id,
                    order_id=o.id,
                    order_item_id=it.id,
                    service_package_template_id=it.service_package_template_id,
                    owner_id=o.user_id,
                    region_scope=it.region_scope,
                    tier=it.tier,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    created_at=datetime.utcnow(),
                )
                session.add(sp)

                for ps in ps_list:
                    entitlement_id = str(uuid4())
                    voucher_code = _voucher_code_v1()
                    qr_payload = _build_qr_payload_v1(
                        secret=qr_sign_secret,
                        entitlement_id=entitlement_id,
                        voucher_code=voucher_code,
                        now_ts=now_ts,
                    )

                    e = Entitlement(
                        id=entitlement_id,
                        user_id=o.user_id,
                        order_id=o.id,
                        entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
                        service_type=ps.service_type,
                        remaining_count=int(ps.total_count),
                        total_count=int(ps.total_count),
                        valid_from=valid_from,
                        valid_until=valid_until,
                        applicable_venues=None,
                        applicable_regions=[it.region_scope],
                        qr_code=qr_payload,
                        voucher_code=voucher_code,
                        status=EntitlementStatus.ACTIVE.value,
                        service_package_instance_id=sp_id,
                        owner_id=o.user_id,
                        activator_id="",
                        current_user_id=o.user_id,
                        created_at=datetime.utcnow(),
                    )
                    validate_entitlement_shape(
                        EntitlementShape(owner_id=e.owner_id, qr_code=e.qr_code, voucher_code=e.voucher_code)
                    )
                    session.add(e)
                    created += 1

    else:
        # PRODUCT（服务类订单）在 v1 不生成权益（阶段5仅覆盖服务包）
        return 0

    await session.flush()
    return created
