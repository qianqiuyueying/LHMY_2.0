"""Admin 仪表盘统计（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> E-11. Admin 仪表盘统计（v1 最小契约）
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.v1.deps import require_admin
from app.models.after_sale_case import AfterSaleCase
from app.models.enums import AfterSaleStatus, OrderType, PaymentStatus, RedemptionStatus, UserEnterpriseBindingStatus
from app.models.order import Order
from app.models.redemption_record import RedemptionRecord
from app.models.service_package_instance import ServicePackageInstance
from app.models.user_enterprise_binding import UserEnterpriseBinding
from app.utils.db import get_session_factory
from app.utils.response import ok

router = APIRouter(tags=["admin-dashboard"])


def _date_range_days(*, days: int) -> list[date]:
    today = datetime.now(tz=UTC).date()
    start = today - timedelta(days=days - 1)
    out: list[date] = []
    d = start
    while d <= today:
        out.append(d)
        d = d + timedelta(days=1)
    return out


def _iso_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


@router.get("/admin/dashboard/summary")
async def admin_dashboard_summary(
    request: Request,
    range: str = "7d",
    _admin=Depends(require_admin),
):
    if range not in {"7d", "30d"}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "range 不合法"})
    days = 7 if range == "7d" else 30
    dates = _date_range_days(days=days)
    start_dt = datetime.combine(dates[0], datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(dates[-1], datetime.max.time(), tzinfo=UTC)

    today = datetime.now(tz=UTC).date()
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    today_end = datetime.combine(today, datetime.max.time(), tzinfo=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 今日：新增会员数（按 service_package_instances.created_at 去重 owner）
        new_member_count = int(
            (
                await session.execute(
                    select(func.count(func.distinct(ServicePackageInstance.owner_id))).where(
                        ServicePackageInstance.created_at >= today_start,
                        ServicePackageInstance.created_at <= today_end,
                    )
                )
            ).scalar()
            or 0
        )

        # 今日：服务包支付成功数（按 paid_at）
        sp_paid_today = int(
            (
                await session.execute(
                    select(func.count()).select_from(Order).where(
                        Order.order_type == OrderType.SERVICE_PACKAGE.value,
                        Order.payment_status == PaymentStatus.PAID.value,
                        Order.paid_at.is_not(None),
                        Order.paid_at >= today_start,
                        Order.paid_at <= today_end,
                    )
                )
            ).scalar()
            or 0
        )

        # 今日：电商支付成功数（PRODUCT，按 paid_at）
        ecommerce_paid_today = int(
            (
                await session.execute(
                    select(func.count()).select_from(Order).where(
                        Order.order_type.in_([OrderType.PRODUCT.value]),
                        Order.payment_status == PaymentStatus.PAID.value,
                        Order.paid_at.is_not(None),
                        Order.paid_at >= today_start,
                        Order.paid_at <= today_end,
                    )
                )
            ).scalar()
            or 0
        )

        # 今日：售后/退款申请数（按 created_at；v1 口径：不区分 type/status）
        refund_request_today = int(
            (
                await session.execute(
                    select(func.count()).select_from(AfterSaleCase).where(
                        AfterSaleCase.created_at >= today_start,
                        AfterSaleCase.created_at <= today_end,
                    )
                )
            ).scalar()
            or 0
        )

        # 今日：核销成功数（按 redemption_time）
        redemption_success_today = int(
            (
                await session.execute(
                    select(func.count()).select_from(RedemptionRecord).where(
                        RedemptionRecord.status == RedemptionStatus.SUCCESS.value,
                        RedemptionRecord.redemption_time >= today_start,
                        RedemptionRecord.redemption_time <= today_end,
                    )
                )
            ).scalar()
            or 0
        )

        # 趋势：服务包支付成功（按 paid_at）
        sp_trend_rows = (
            await session.execute(
                select(func.date(Order.paid_at).label("d"), func.count().label("c"))
                .select_from(Order)
                .where(
                    Order.order_type == OrderType.SERVICE_PACKAGE.value,
                    Order.payment_status == PaymentStatus.PAID.value,
                    Order.paid_at.is_not(None),
                    Order.paid_at >= start_dt,
                    Order.paid_at <= end_dt,
                )
                .group_by(func.date(Order.paid_at))
            )
        ).all()
        sp_by_date = {str(d): int(c) for d, c in sp_trend_rows if d is not None}

        # 趋势：电商支付成功（按 paid_at）
        ecommerce_trend_rows = (
            await session.execute(
                select(func.date(Order.paid_at).label("d"), func.count().label("c"))
                .select_from(Order)
                .where(
                    Order.order_type.in_([OrderType.PRODUCT.value]),
                    Order.payment_status == PaymentStatus.PAID.value,
                    Order.paid_at.is_not(None),
                    Order.paid_at >= start_dt,
                    Order.paid_at <= end_dt,
                )
                .group_by(func.date(Order.paid_at))
            )
        ).all()
        ecommerce_by_date = {str(d): int(c) for d, c in ecommerce_trend_rows if d is not None}

        # 趋势：核销成功（按 redemption_time）
        redeem_trend_rows = (
            await session.execute(
                select(func.date(RedemptionRecord.redemption_time).label("d"), func.count().label("c"))
                .select_from(RedemptionRecord)
                .where(
                    RedemptionRecord.status == RedemptionStatus.SUCCESS.value,
                    RedemptionRecord.redemption_time >= start_dt,
                    RedemptionRecord.redemption_time <= end_dt,
                )
                .group_by(func.date(RedemptionRecord.redemption_time))
            )
        ).all()
        redeem_by_date = {str(d): int(c) for d, c in redeem_trend_rows if d is not None}

        # 待办：退款待审核数（全量 UNDER_REVIEW）
        refund_under_review_all = int(
            (
                await session.execute(
                    select(func.count()).select_from(AfterSaleCase).where(
                        AfterSaleCase.status == AfterSaleStatus.UNDER_REVIEW.value
                    )
                )
            ).scalar()
            or 0
        )

        # 待办：异常订单数（v1 仅 payment_status=FAILED）
        abnormal_order_count = int(
            (
                await session.execute(
                    select(func.count()).select_from(Order).where(Order.payment_status == PaymentStatus.FAILED.value)
                )
            ).scalar()
            or 0
        )

        # 待办：企业绑定待处理数
        enterprise_binding_pending = int(
            (
                await session.execute(
                    select(func.count()).select_from(UserEnterpriseBinding).where(
                        UserEnterpriseBinding.status == UserEnterpriseBindingStatus.PENDING.value
                    )
                )
            ).scalar()
            or 0
        )

    def _series(by_date: dict[str, int]) -> list[dict]:
        out: list[dict] = []
        for d in dates:
            key = _iso_date(d)
            out.append({"date": key, "count": int(by_date.get(key, 0))})
        return out

    return ok(
        data={
            "range": range,
            "today": {
                "newMemberCount": new_member_count,
                "servicePackagePaidCount": sp_paid_today,
                "ecommercePaidCount": ecommerce_paid_today,
                "refundRequestCount": refund_request_today,
                "redemptionSuccessCount": redemption_success_today,
            },
            "trends": {
                "servicePackageOrders": _series(sp_by_date),
                "ecommerceOrders": _series(ecommerce_by_date),
                "redemptions": _series(redeem_by_date),
            },
            "todos": {
                "refundUnderReviewCount": refund_under_review_all,
                "abnormalOrderCount": abnormal_order_count,
                "enterpriseBindingPendingCount": enterprise_binding_pending,
            },
        },
        request_id=request.state.request_id,
    )

