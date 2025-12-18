"""权益二维码 payload 签名（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 权益二维码 payload 签名规则（v1 最小可执行）
- specs/health-services-platform/tasks.md -> 阶段5-29

口径（与 design.md 对齐）：
- payload 字段（固定顺序）：entitlementId、voucherCode、ts、nonce、sign
- canonical：entitlementId={entitlementId}&voucherCode={voucherCode}&ts={ts}&nonce={nonce}
- sign：HMAC-SHA256(secret, canonical) -> hex（小写）
- 有效期：abs(now-ts) <= 10min

说明：
- v1 约束：签名密钥仅存后端（环境变量），不得下发前端。
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from urllib.parse import parse_qs


def build_canonical(*, entitlement_id: str, voucher_code: str, ts: int, nonce: str) -> str:
    return f"entitlementId={entitlement_id}&voucherCode={voucher_code}&ts={ts}&nonce={nonce}"


def sign_payload(*, secret: str, entitlement_id: str, voucher_code: str, ts: int, nonce: str) -> str:
    canonical = build_canonical(entitlement_id=entitlement_id, voucher_code=voucher_code, ts=ts, nonce=nonce)
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def build_payload_text(*, entitlement_id: str, voucher_code: str, ts: int, nonce: str, sign: str) -> str:
    # 固定顺序输出，便于前端稳定生成二维码文本
    return (
        f"entitlementId={entitlement_id}"
        f"&voucherCode={voucher_code}"
        f"&ts={ts}"
        f"&nonce={nonce}"
        f"&sign={sign}"
    )


@dataclass(frozen=True)
class PayloadParts:
    entitlement_id: str
    voucher_code: str
    ts: int
    nonce: str
    sign: str


def parse_payload_text(payload_text: str) -> PayloadParts:
    """解析二维码 payload 文本（querystring 形态）。"""

    parsed = parse_qs(payload_text, keep_blank_values=True, strict_parsing=False)

    def _get_one(key: str) -> str:
        values = parsed.get(key)
        if not values:
            raise ValueError(f"missing {key}")
        return str(values[0])

    entitlement_id = _get_one("entitlementId")
    voucher_code = _get_one("voucherCode")
    ts_raw = _get_one("ts")
    nonce = _get_one("nonce")
    sign = _get_one("sign")
    try:
        ts = int(ts_raw)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("invalid ts") from exc

    return PayloadParts(entitlement_id=entitlement_id, voucher_code=voucher_code, ts=ts, nonce=nonce, sign=sign)


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    error_code: str | None = None
    parts: PayloadParts | None = None


def verify_payload_text(*, secret: str, payload_text: str, now_ts: int) -> VerifyResult:
    """校验 payload 文本（包含签名与有效期）。"""

    try:
        parts = parse_payload_text(payload_text)
    except Exception:
        return VerifyResult(ok=False, error_code="QR_SIGN_INVALID", parts=None)

    # 10 分钟有效期
    if abs(now_ts - parts.ts) > 10 * 60:
        return VerifyResult(ok=False, error_code="QR_SIGN_EXPIRED", parts=parts)

    expected = sign_payload(
        secret=secret,
        entitlement_id=parts.entitlement_id,
        voucher_code=parts.voucher_code,
        ts=parts.ts,
        nonce=parts.nonce,
    )
    if not hmac.compare_digest(expected, parts.sign):
        return VerifyResult(ok=False, error_code="QR_SIGN_INVALID", parts=parts)

    return VerifyResult(ok=True, error_code=None, parts=parts)

