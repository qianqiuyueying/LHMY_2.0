"""库存相关后台任务（占位）。

v2 目标：
- 支持“下单占用库存 -> 超时释放”

当前阶段：
- 仅提供一个周期任务占位，确保 Celery worker/beat 可启动与可运行。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

from celery.schedules import crontab

from app.celery_app import celery_app
from app.models.enums import PaymentStatus, ProductFulfillmentType
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.utils.db import get_session_factory
from app.utils.settings import settings
from sqlalchemy import select


@cast(Any, celery_app.on_after_configure).connect
def _setup_periodic_tasks(sender, **_kwargs) -> None:
    # v2 占位：每分钟扫描一次超时订单并释放库存（实现将在电商能力落地时补齐）
    sender.add_periodic_task(
        crontab(minute="*/1"),
        cast(Any, release_expired_stock_reservations).s(),
        name="release_expired_stock",
    )


@celery_app.task(name="inventory.release_expired_stock_reservations")
def release_expired_stock_reservations() -> dict:
    async def _run() -> int:
        now = datetime.now(tz=UTC).replace(tzinfo=None)

        session_factory = get_session_factory()
        async with session_factory() as session:
            # 仅释放：待支付 + 已到期 + 物流商品订单
            orders: list[Order] = list(
                (
                    await session.scalars(
                    select(Order)
                    .where(
                        Order.payment_status == PaymentStatus.PENDING.value,
                        Order.fulfillment_type == ProductFulfillmentType.PHYSICAL_GOODS.value,
                        Order.reservation_expires_at.is_not(None),
                        Order.reservation_expires_at < now,
                    )
                    .order_by(Order.created_at.asc())
                    .limit(200)
                    )
                ).all()
            )

            if not orders:
                return 0

            released = 0
            for o in orders:
                items: list[OrderItem] = list((await session.scalars(select(OrderItem).where(OrderItem.order_id == o.id))).all())
                # 仅对 PRODUCT 明细扣预占（SERVICE_PACKAGE 不走库存）
                product_ids = [it.item_id for it in items if it.item_type == "PRODUCT"]
                if product_ids:
                    products: list[Product] = list((await session.scalars(select(Product).where(Product.id.in_(product_ids)))).all())
                    prod_map = {p.id: p for p in products}
                    for it in items:
                        if it.item_type != "PRODUCT":
                            continue
                        p = prod_map.get(it.item_id)
                        if p is None:
                            continue
                        qty = int(it.quantity or 0)
                        if qty <= 0:
                            continue
                        # 防御：不让 reserved_stock 变负
                        p.reserved_stock = max(0, int(p.reserved_stock or 0) - qty)

                # 标记订单已关闭（最小：置为 FAILED 并清空到期时间，避免重复释放）
                o.payment_status = PaymentStatus.FAILED.value
                o.reservation_expires_at = None
                released += 1

            await session.commit()
            return released

    released = asyncio.run(_run())
    return {"ok": True, "released": int(released)}


