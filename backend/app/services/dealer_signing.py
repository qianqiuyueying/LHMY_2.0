"""经销商参数签名（sign）工具（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 经销商参数签名（sign）规则

签名规则：
- canonical：dealerId={dealerId}&ts={ts}&nonce={nonce}
- HMAC-SHA256(secret, canonical) -> hex（小写）
- 有效期：abs(now-ts) <= 10min
"""

from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass


def build_canonical(*, dealer_id: str, ts: int, nonce: str) -> str:
    return f"dealerId={dealer_id}&ts={ts}&nonce={nonce}"


def sign_params(*, secret: str, dealer_id: str, ts: int, nonce: str) -> str:
    canonical = build_canonical(dealer_id=dealer_id, ts=ts, nonce=nonce)
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    error_code: str | None = None


def verify_params(*, secret: str, dealer_id: str, ts: int, nonce: str, sign: str, now_ts: int) -> VerifyResult:
    # 10 分钟有效期
    if abs(now_ts - ts) > 10 * 60:
        return VerifyResult(ok=False, error_code="DEALER_SIGN_EXPIRED")

    expected = sign_params(secret=secret, dealer_id=dealer_id, ts=ts, nonce=nonce)
    if not hmac.compare_digest(expected, sign):
        return VerifyResult(ok=False, error_code="DEALER_SIGN_INVALID")

    return VerifyResult(ok=True, error_code=None)
