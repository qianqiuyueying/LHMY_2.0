"""属性测试：经销商参数解析和防篡改（属性5）。

规格来源：
- specs/health-services-platform/design.md -> 属性 5：经销商参数解析和防篡改
- specs/health-services-platform/design.md -> 经销商参数签名（sign）规则

断言：
- 使用同一 secret 生成的签名，在有效期内应校验通过。
- 任一字段（dealerId/ts/nonce）被篡改且 sign 不变时，应校验失败。
- 超过有效期，应返回过期错误。
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.dealer_signing import sign_params, verify_params


def _safe_text(min_size: int = 1, max_size: int = 36):
    # 避免 & = ? 等可能影响 canonical 的字符
    alphabet = st.characters(blacklist_characters=["&", "=", "?", "#", " ", "\n", "\r", "\t"], min_codepoint=33, max_codepoint=126)
    return st.text(alphabet=alphabet, min_size=min_size, max_size=max_size)


@given(
    secret=_safe_text(8, 64),
    dealer_id=_safe_text(1, 36),
    nonce=_safe_text(6, 64),
    ts=st.integers(min_value=1, max_value=2_000_000_000),
)
def test_property_5_verify_ok_and_tamper_detected(secret: str, dealer_id: str, nonce: str, ts: int):
    now_ts = ts  # 保证在有效期内
    sign = sign_params(secret=secret, dealer_id=dealer_id, ts=ts, nonce=nonce)

    assert verify_params(secret=secret, dealer_id=dealer_id, ts=ts, nonce=nonce, sign=sign, now_ts=now_ts).ok is True

    # 篡改 dealerId
    bad_dealer_id = dealer_id + "X"
    assert verify_params(secret=secret, dealer_id=bad_dealer_id, ts=ts, nonce=nonce, sign=sign, now_ts=now_ts).ok is False

    # 篡改 ts
    bad_ts = ts + 1
    assert verify_params(secret=secret, dealer_id=dealer_id, ts=bad_ts, nonce=nonce, sign=sign, now_ts=now_ts).ok is False

    # 篡改 nonce
    bad_nonce = nonce + "Y"
    assert verify_params(secret=secret, dealer_id=dealer_id, ts=ts, nonce=bad_nonce, sign=sign, now_ts=now_ts).ok is False


@given(
    secret=_safe_text(8, 64),
    dealer_id=_safe_text(1, 36),
    nonce=_safe_text(6, 64),
    ts=st.integers(min_value=1, max_value=2_000_000_000),
    offset=st.integers(min_value=10 * 60 + 1, max_value=30 * 60),
)
def test_property_5_verify_expired(secret: str, dealer_id: str, nonce: str, ts: int, offset: int):
    sign = sign_params(secret=secret, dealer_id=dealer_id, ts=ts, nonce=nonce)
    now_ts = ts + offset

    r = verify_params(secret=secret, dealer_id=dealer_id, ts=ts, nonce=nonce, sign=sign, now_ts=now_ts)
    assert r.ok is False
    assert r.error_code == "DEALER_SIGN_EXPIRED"
