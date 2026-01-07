"""H5 只读配置下发（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> H. H5 只读配置下发（v1 最小契约）
- specs/health-services-platform/design.md -> SystemConfig key 约定（H5_*）

说明：
- v1 使用 SystemConfig 作为最小承载；仅提供读侧接口。
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.models.bind_token import BindToken
from app.models.card import Card
from app.models.enums import CommonEnabledStatus
from app.models.enums import LegalAgreementStatus
from app.models.enums import DealerLinkStatus, DealerStatus
from app.models.dealer import Dealer
from app.models.dealer_link import DealerLink
from app.models.enums import CardStatus
from app.models.order import Order
from app.models.enums import PaymentStatus
from app.models.package_service import PackageService
from app.models.sellable_card import SellableCard
from app.models.service_package import ServicePackage
from app.models.legal_agreement import LegalAgreement
from app.models.system_config import SystemConfig
from app.utils.db import get_session_factory
from app.utils.response import ok
from app.utils.datetime_iso import iso as _iso
from app.services.wechat_h5_jssdk import build_wechat_jssdk_config

router = APIRouter(tags=["h5-config"])

_KEY_FAQ_TERMS = "H5_LANDING_FAQ_TERMS"
_KEY_SERVICE_AGREEMENT = "H5_SERVICE_AGREEMENT"
_KEY_MINI_PROGRAM_LAUNCH = "H5_MINI_PROGRAM_LAUNCH"
_LEGAL_CODE_H5_BUY_AGREEMENT = "H5_BUY_AGREEMENT"


def _assert_dealer_link_usable(*, link: DealerLink, now_utc) -> None:
    # 兼容：status 可能尚未被惰性更新为 EXPIRED，因此此处做一次兜底判断
    if str(link.status) != DealerLinkStatus.ENABLED.value:
        raise ValueError("LINK_NOT_ENABLED")
    if link.valid_from and link.valid_from.replace(tzinfo=None) > now_utc.replace(tzinfo=None):
        raise ValueError("LINK_NOT_YET_VALID")
    if link.valid_until and link.valid_until.replace(tzinfo=None) < now_utc.replace(tzinfo=None):
        raise ValueError("LINK_EXPIRED")


async def _get_enabled_value(key: str) -> dict | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        cfg = (
            await session.scalars(
                select(SystemConfig)
                .where(SystemConfig.key == key, SystemConfig.status == CommonEnabledStatus.ENABLED.value)
                .limit(1)
            )
        ).first()
    if cfg is None:
        return None
    return cfg.value_json or {}

async def _get_published_legal(code: str) -> LegalAgreement | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (
            await session.scalars(
                select(LegalAgreement).where(
                    LegalAgreement.code == code, LegalAgreement.status == LegalAgreementStatus.PUBLISHED.value
                )
            )
        ).first()
    return row


@router.get("/h5/landing/faq-terms")
async def h5_get_faq_terms(request: Request):
    raw = await _get_enabled_value(_KEY_FAQ_TERMS)
    if raw is None:
        return ok(data={"items": [], "termsText": "", "version": "0"}, request_id=request.state.request_id)

    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []
    out_items: list[dict] = []
    for x in items:
        if not isinstance(x, dict):
            continue
        out_items.append({"q": str(x.get("q") or ""), "a": str(x.get("a") or "")})

    return ok(
        data={
            "items": out_items,
            "termsText": str(raw.get("termsText") or ""),
            "version": str(raw.get("version") or "0"),
        },
        request_id=request.state.request_id,
    )


@router.get("/h5/legal/service-agreement")
async def h5_get_service_agreement(request: Request):
    # 优先：协议中心（REQ-ADMIN-P0-008）
    row = await _get_published_legal(_LEGAL_CODE_H5_BUY_AGREEMENT)
    if row is not None:
        return ok(
            data={"title": row.title, "contentHtml": row.content_html, "version": row.version},
            request_id=request.state.request_id,
        )

    # 兼容：历史 SystemConfig（v1）
    raw = await _get_enabled_value(_KEY_SERVICE_AGREEMENT)
    if raw is None:
        return ok(data={"title": "", "contentHtml": "", "version": "0"}, request_id=request.state.request_id)

    return ok(
        data={
            "title": str(raw.get("title") or ""),
            "contentHtml": str(raw.get("contentHtml") or ""),
            "version": str(raw.get("version") or "0"),
        },
        request_id=request.state.request_id,
    )


@router.get("/h5/mini-program/launch")
async def h5_get_mini_program_launch(request: Request):
    raw = await _get_enabled_value(_KEY_MINI_PROGRAM_LAUNCH)
    if raw is None:
        return ok(data={"appid": "", "path": "", "fallbackText": None, "version": "0"}, request_id=request.state.request_id)

    return ok(
        data={
            "appid": str(raw.get("appid") or ""),
            "path": str(raw.get("path") or ""),
            "fallbackText": raw.get("fallbackText"),
            "version": str(raw.get("version") or "0"),
        },
        request_id=request.state.request_id,
    )


@router.get("/h5/wechat/jssdk-config")
async def h5_get_wechat_jssdk_config(request: Request, url: str):
    """H5：微信 JS-SDK 初始化参数（用于 wx-open-launch-weapp，一键拉起小程序）。"""

    try:
        cfg = await build_wechat_jssdk_config(url=url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "微信 JS-SDK 配置生成失败"}) from exc

    return ok(
        data={"appId": cfg.appId, "timestamp": cfg.timestamp, "nonceStr": cfg.nonceStr, "signature": cfg.signature},
        request_id=request.state.request_id,
    )


@router.get("/h5/dealer-links/{dealerLinkId}")
async def h5_get_dealer_link(request: Request, dealerLinkId: str):
    """H5 投放链接解析（只读，无需登录）。

    口径：以 dealerLinkId 作为长期投放主入口；仅返回 ENABLED 且未过期链接的数据。
    """
    dealer_link_id = str(dealerLinkId or "").strip()
    if not dealer_link_id:
        return ok(data={"dealer": None, "sellableCard": None, "link": None}, request_id=request.state.request_id)

    session_factory = get_session_factory()
    async with session_factory() as session:
        link = (await session.scalars(select(DealerLink).where(DealerLink.id == dealer_link_id).limit(1))).first()
        if link is None:
            # 404：链接不存在
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "投放链接不存在"})

        from datetime import UTC, datetime  # noqa: WPS433

        now = datetime.now(tz=UTC)
        try:
            _assert_dealer_link_usable(link=link, now_utc=now)
        except ValueError as e:
            from fastapi import HTTPException  # noqa: WPS433

            code = str(e)
            if code == "LINK_EXPIRED":
                raise HTTPException(status_code=403, detail={"code": "DEALER_LINK_EXPIRED", "message": "投放链接已过期"})
            raise HTTPException(status_code=403, detail={"code": "DEALER_LINK_DISABLED", "message": "投放链接不可用"})

        dealer = (await session.scalars(select(Dealer).where(Dealer.id == link.dealer_id).limit(1))).first()
        if dealer is None:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "经销商不存在"})
        if str(dealer.status) != DealerStatus.ACTIVE.value:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "经销商已停用"})

        # vNext：该接口仅解析“经销商入口链接”（dealerLinkId），不强绑定某个 sellableCard
        sellable_card = None

    return ok(
        data={
            "dealer": {"id": dealer.id, "name": dealer.name},
            "sellableCard": None,
            "link": {
                "id": link.id,
                "status": link.status,
                "validFrom": _iso(link.valid_from),
                "validUntil": _iso(link.valid_until),
            },
        },
        request_id=request.state.request_id,
    )


@router.get("/h5/dealer-links/{dealerLinkId}/cards/{sellableCardId}")
async def h5_get_dealer_card(request: Request, dealerLinkId: str, sellableCardId: str):
    """H5：经销商入口 + 指定卡详情（只读，无需登录）。

    门禁：sellableCardId 必须存在于该经销商“已生成投放链接且可用”的卡列表中。
    """
    dealer_link_id = str(dealerLinkId or "").strip()
    card_id = str(sellableCardId or "").strip()
    if not dealer_link_id or not card_id:
        from fastapi import HTTPException  # noqa: WPS433

        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "dealerLinkId 与 sellableCardId 必填"})

    from datetime import UTC, datetime  # noqa: WPS433

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        seed = (await session.scalars(select(DealerLink).where(DealerLink.id == dealer_link_id).limit(1))).first()
        if seed is None:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "投放链接不存在"})

        # 校验 seed 链接本身可用（作为入口身份）
        try:
            _assert_dealer_link_usable(link=seed, now_utc=now)
        except ValueError:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=403, detail={"code": "DEALER_LINK_DISABLED", "message": "投放链接不可用"})

        dealer_id = str(seed.dealer_id)
        dealer = (await session.scalars(select(Dealer).where(Dealer.id == dealer_id).limit(1))).first()
        if dealer is None:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "经销商不存在"})
        if str(dealer.status) != DealerStatus.ACTIVE.value:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "经销商已停用"})

        # 校验该卡是否在 dealer 的“可用投放链接”里（授权门禁）
        links = (
            await session.scalars(
                select(DealerLink).where(
                    DealerLink.dealer_id == dealer_id,
                    DealerLink.status == DealerLinkStatus.ENABLED.value,
                    DealerLink.sellable_card_id == card_id,
                )
            )
        ).all()
        ok_link = None
        for l in links:
            try:
                _assert_dealer_link_usable(link=l, now_utc=now)
                ok_link = l
                break
            except ValueError:
                continue
        if ok_link is None:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "该经销商无权售卖该卡"})

        c = (await session.scalars(select(SellableCard).where(SellableCard.id == card_id).limit(1))).first()
        if c is None:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "可售卡不存在"})
        if str(c.status) != CommonEnabledStatus.ENABLED.value:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "可售卡已停用"})

        # 服务摘要（用于详情页/购卡页）
        tid = str(c.service_package_template_id or "").strip()
        svcs = (
            await session.scalars(select(PackageService).where(PackageService.service_package_id == tid))
        ).all()
        services = [{"serviceType": s.service_type, "totalCount": int(s.total_count)} for s in svcs]
        services.sort(key=lambda x: str(x.get("serviceType") or ""))

    return ok(
        data={
            "dealer": {"id": dealer.id, "name": dealer.name},
            "sellableCard": {
                "id": c.id,
                "name": c.name,
                "regionLevel": c.region_level,
                "priceOriginal": float(c.price_original or 0),
                "servicePackageTemplateId": c.service_package_template_id,
                "services": services,
            },
            "link": {"id": seed.id, "status": seed.status, "validFrom": _iso(seed.valid_from), "validUntil": _iso(seed.valid_until)},
        },
        request_id=request.state.request_id,
    )


@router.get("/h5/dealer-links/{dealerLinkId}/cards")
async def h5_list_dealer_cards(request: Request, dealerLinkId: str):
    """H5：按经销商投放链接列出该经销商可售卡（仅限“已生成投放链接且可用”的卡）。"""
    dealer_link_id = str(dealerLinkId or "").strip()
    if not dealer_link_id:
        return ok(data={"items": []}, request_id=request.state.request_id)

    from datetime import UTC, datetime  # noqa: WPS433

    now = datetime.now(tz=UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        seed = (await session.scalars(select(DealerLink).where(DealerLink.id == dealer_link_id).limit(1))).first()
        if seed is None:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "投放链接不存在"})

        # 基于 seed 链接解析 dealerId（无论 seed 是否绑定卡）
        dealer_id = str(seed.dealer_id)
        dealer = (await session.scalars(select(Dealer).where(Dealer.id == dealer_id).limit(1))).first()
        if dealer is None:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "经销商不存在"})
        if str(dealer.status) != DealerStatus.ACTIVE.value:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "经销商已停用"})

        # 拉取该 dealer 下所有启用且未过期的“卡链接”（sellableCardId 非空）
        links = (
            await session.scalars(
                select(DealerLink)
                .where(
                    DealerLink.dealer_id == dealer_id,
                    DealerLink.status == DealerLinkStatus.ENABLED.value,
                    DealerLink.sellable_card_id.is_not(None),
                    DealerLink.sellable_card_id != "",
                )
                .order_by(DealerLink.created_at.desc())
            )
        ).all()

        # 按 sellableCardId 去重：优先取最新链接
        picked: dict[str, DealerLink] = {}
        for l in links:
            # 兜底过期判断（避免 status 未惰性更新）
            try:
                _assert_dealer_link_usable(link=l, now_utc=now)
            except ValueError:
                continue
            sid = str(l.sellable_card_id or "").strip()
            if not sid:
                continue
            if sid not in picked:
                picked[sid] = l

        if not picked:
            return ok(data={"items": []}, request_id=request.state.request_id)

        sellable_card_ids = list(picked.keys())
        cards = (
            await session.scalars(
                select(SellableCard).where(
                    SellableCard.id.in_(sellable_card_ids),
                    SellableCard.status == CommonEnabledStatus.ENABLED.value,
                )
            )
        ).all()
        card_by_id = {c.id: c for c in cards}

        # 预取服务包模板与其服务明细（用于“服务类别×次数”展示）
        template_ids = list({str(c.service_package_template_id or "").strip() for c in cards if c is not None})
        template_ids = [x for x in template_ids if x]
        template_by_id: dict[str, ServicePackage] = {}
        services_by_template: dict[str, list[dict]] = {}
        if template_ids:
            templates = (
                await session.scalars(select(ServicePackage).where(ServicePackage.id.in_(template_ids)))
            ).all()
            template_by_id = {t.id: t for t in templates}

            svcs = (
                await session.scalars(select(PackageService).where(PackageService.service_package_id.in_(template_ids)))
            ).all()
            for s in svcs:
                services_by_template.setdefault(s.service_package_id, []).append(
                    {"serviceType": s.service_type, "totalCount": int(s.total_count)}
                )

            # 保持稳定顺序：按 serviceType 排一下（避免同一模板多次返回顺序抖动）
            for tid, arr in services_by_template.items():
                arr.sort(key=lambda x: str(x.get("serviceType") or ""))

        out: list[dict] = []
        for sid, l in picked.items():
            c = card_by_id.get(sid)
            if c is None:
                continue
            services = services_by_template.get(str(c.service_package_template_id or "").strip(), [])
            out.append(
                {
                    "dealerLinkId": l.id,
                    "sellableCard": {
                        "id": c.id,
                        "name": c.name,
                        "regionLevel": c.region_level,
                        "priceOriginal": float(c.price_original or 0),
                        "servicePackageTemplateId": c.service_package_template_id,
                        "services": services,
                    },
                }
            )

        return ok(data={"items": out}, request_id=request.state.request_id)


@router.get("/h5/orders/{orderId}/bind-token")
async def h5_get_order_bind_token(request: Request, orderId: str):
    """H5：按订单号读取 bind_token（只读，无需登录）。

    v1 约束：
    - Card.id = Order.id（一单一张卡）
    - 返回未过期且未使用的 bind_token；若支付回调尚未发卡则返回 null
    """

    oid = str(orderId or "").strip()
    if not oid:
        from fastapi import HTTPException  # noqa: WPS433

        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "orderId 必填"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        o = (await session.scalars(select(Order).where(Order.id == oid).limit(1))).first()
        if o is None:
            from fastapi import HTTPException  # noqa: WPS433

            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "订单不存在"})

        card_id = oid
        card = (await session.scalars(select(Card).where(Card.id == card_id).limit(1))).first()
        if card is None:
            # 支付回调可能尚未发卡：返回空字段，H5 可轮询
            return ok(
                data={"orderId": oid, "cardId": card_id, "cardStatus": None, "bindToken": None, "expiresAt": None},
                request_id=request.state.request_id,
            )

        card_status = str(card.status or "")
        if card_status == CardStatus.BOUND.value:
            # 已绑定：不再返回 token
            return ok(
                data={
                    "orderId": oid,
                    "cardId": card_id,
                    "cardStatus": CardStatus.BOUND.value,
                    "bindToken": None,
                    "expiresAt": None,
                },
                request_id=request.state.request_id,
            )

        # 仅当订单已支付成功且卡未绑定时，才返回 token（避免“未支付也给入口”）
        if str(o.payment_status or "") != PaymentStatus.PAID.value:
            return ok(
                data={
                    "orderId": oid,
                    "cardId": card_id,
                    "cardStatus": CardStatus.UNBOUND.value,
                    "bindToken": None,
                    "expiresAt": None,
                },
                request_id=request.state.request_id,
            )

        now = datetime.now(tz=UTC).replace(tzinfo=None)
        bt = (
            await session.scalars(
                select(BindToken)
                .where(
                    BindToken.card_id == card_id,
                    BindToken.used_at.is_(None),
                    BindToken.expires_at > now,
                )
                .limit(1)
            )
        ).first()
        return ok(
            data={
                "orderId": oid,
                "cardId": card_id,
                "cardStatus": CardStatus.UNBOUND.value,
                "bindToken": (bt.token if bt else None),
                "expiresAt": (bt.expires_at.isoformat() if bt and bt.expires_at else None),
            },
            request_id=request.state.request_id,
        )

