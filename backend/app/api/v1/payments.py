"""支付回调 Webhook（REQ-P0-001）。

规格来源：
- specs/health-services-platform/后端升级需求与变更清单（v1）.md -> REQ-P0-001
- specs/health-services-platform/design.md -> 订单支付（orders.paymentStatus）/支付记录（payments）

实现说明（v1）：
- 路径：POST /api/v1/payments/wechat/notify
- 使用微信支付 v3 通知报文：验签（平台证书）+ 解密（APIv3Key）
- 幂等：重复回调由 mark_payment_succeeded 内部状态机与幂等逻辑兜底
- 响应：按微信支付通知规范返回 {code,message}

注意：design.md 未定义对接微信支付“下单/支付参数签名”的完整契约，本实现仅覆盖回调侧。
"""

from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509 import load_pem_x509_certificate
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.models.payment import Payment
from app.services.payment_callbacks import mark_payment_succeeded
from app.utils.db import get_session_factory
from app.utils.settings import settings

router = APIRouter(tags=["payments"])


def _wechat_fail(*, status_code: int, message: str) -> JSONResponse:
    # 微信支付回调要求返回固定结构
    return JSONResponse(status_code=status_code, content={"code": "FAIL", "message": message})


def _wechat_success() -> JSONResponse:
    return JSONResponse(status_code=200, content={"code": "SUCCESS", "message": "成功"})

def _http_exc_message(exc: HTTPException, fallback: str) -> str:
    if isinstance(exc.detail, dict):
        msg = exc.detail.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()
    return fallback


def _load_platform_certificate_pem() -> bytes:
    raw = (settings.wechat_pay_platform_cert_pem_or_path or "").strip()
    if not raw:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "缺少微信支付平台证书配置"})

    if raw.startswith("-----BEGIN"):
        return raw.encode("utf-8")

    # 否则视为文件路径
    try:
        with open(raw, "rb") as f:  # noqa: PTH123
            return f.read()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": "无法读取微信支付平台证书文件"},
        ) from exc


def _verify_wechatpay_signature(*, headers: dict[str, str], body_text: str) -> None:
    timestamp = headers.get("wechatpay-timestamp", "").strip()
    nonce = headers.get("wechatpay-nonce", "").strip()
    signature_b64 = headers.get("wechatpay-signature", "").strip()
    serial = headers.get("wechatpay-serial", "").strip()

    if not (timestamp and nonce and signature_b64 and serial):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "缺少微信支付验签头"})

    expected_serial = (settings.wechat_pay_platform_cert_serial or "").strip()
    if expected_serial and serial != expected_serial:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "微信支付证书序列号不匹配"})

    message = f"{timestamp}\n{nonce}\n{body_text}\n".encode("utf-8")
    try:
        sig = base64.b64decode(signature_b64)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "微信支付签名格式错误"}) from exc

    cert = load_pem_x509_certificate(_load_platform_certificate_pem())
    pub = cert.public_key()

    try:
        # 微信支付平台证书（v3）为 RSA；类型收窄以满足静态检查，并防御配置错误。
        if isinstance(pub, rsa.RSAPublicKey):
            pub.verify(sig, message, padding.PKCS1v15(), hashes.SHA256())
        elif isinstance(pub, ec.EllipticCurvePublicKey):
            # 兜底：若未来证书切换为 ECC，这里也可验签
            pub.verify(sig, message, ec.ECDSA(hashes.SHA256()))
        else:
            raise HTTPException(
                status_code=500,
                detail={"code": "INTERNAL_ERROR", "message": "微信支付平台证书公钥类型不支持"},
            )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "微信支付签名校验失败"}) from exc


def _decrypt_wechatpay_resource(*, resource: dict[str, Any]) -> dict[str, Any]:
    api_v3_key = (settings.wechat_pay_api_v3_key or "").strip()
    if len(api_v3_key) != 32:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "微信支付 APIv3Key 配置不合法"})

    if resource.get("algorithm") != "AEAD_AES_256_GCM":
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "resource.algorithm 不支持"})

    nonce = str(resource.get("nonce") or "").encode("utf-8")
    associated_data = str(resource.get("associated_data") or "").encode("utf-8")
    ciphertext_b64 = str(resource.get("ciphertext") or "")
    if not (nonce and ciphertext_b64):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "resource 字段不完整"})

    try:
        ciphertext = base64.b64decode(ciphertext_b64)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "resource.ciphertext 不合法"}) from exc

    aesgcm = AESGCM(api_v3_key.encode("utf-8"))
    try:
        plaintext = aesgcm.decrypt(nonce=nonce, data=ciphertext, associated_data=associated_data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "微信支付报文解密失败"}) from exc

    try:
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "解密报文不是合法 JSON"}) from exc


@router.post("/payments/wechat/notify")
async def wechat_pay_notify(request: Request):
    # 微信支付要求使用“原始 body”参与验签，因此这里不用 Pydantic 直接解析。
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8") if body_bytes else ""

    headers = {k.lower(): v for k, v in request.headers.items()}

    try:
        _verify_wechatpay_signature(headers=headers, body_text=body_text)
    except HTTPException as exc:
        # 按微信侧协议返回 FAIL（非 2xx 会触发重试）
        return _wechat_fail(status_code=exc.status_code, message=_http_exc_message(exc, "验签失败"))

    try:
        payload = json.loads(body_text) if body_text else {}
    except Exception:
        return _wechat_fail(status_code=400, message="body 不是合法 JSON")

    resource = payload.get("resource")
    if not isinstance(resource, dict):
        return _wechat_fail(status_code=400, message="缺少 resource")

    try:
        transaction = _decrypt_wechatpay_resource(resource=resource)
    except HTTPException as exc:
        return _wechat_fail(status_code=exc.status_code, message=_http_exc_message(exc, "解密失败"))

    # v1 口径：以 out_trade_no 作为本系统订单号（Order.id）
    order_id = str(transaction.get("out_trade_no") or "").strip()
    if not order_id:
        return _wechat_fail(status_code=400, message="缺少 out_trade_no")

    session_factory = get_session_factory()
    async with session_factory() as session:
        p = (
            await session.scalars(
                select(Payment)
                .where(Payment.order_id == order_id)
                .order_by(Payment.created_at.desc())
                .limit(1)
            )
        ).first()
        if p is None:
            return _wechat_fail(status_code=404, message="支付记录不存在")

        # 幂等：mark_payment_succeeded 内部会对订单状态进行兜底
        await mark_payment_succeeded(
            session=session,
            order_id=order_id,
            payment_id=p.id,
            provider_payload={"wechat": transaction, "notify": {"id": payload.get("id"), "eventType": payload.get("event_type")}},
        )

    return _wechat_success()
