"""属性测试：虚拟服务券生成完整性（属性2）。

规格来源：
- specs/health-services-platform/design.md -> 属性 21：权益生成双形态完整性
- specs/health-services-platform/design.md -> 权益二维码 payload 签名规则（v1 最小可执行）
- specs/health-services-platform/tasks.md -> 阶段5-28.4（Property 2）

v1 最小断言：
- 任意权益都应具备“双形态”：qrCode（payload 文本）与 voucherCode（券码）
- qrCode payload 的签名可被服务端校验（10分钟有效期）
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.entitlement_qr_signing import build_payload_text, sign_payload, verify_payload_text
from app.services.entitlement_rules import EntitlementShape, validate_entitlement_shape


_SECRET = "unit_test_secret"


@given(
    # v1：ownerId/entitlementId 均为 UUID（URL-safe）
    owner_id=st.from_regex(r"[A-Za-z0-9_-]{1,36}", fullmatch=True),
    entitlement_id=st.from_regex(r"[A-Za-z0-9_-]{1,36}", fullmatch=True),
    voucher_code=st.from_regex(r"[0-9A-F]{16}", fullmatch=True),
    ts=st.integers(min_value=1, max_value=2_000_000_000),
    # nonce 在二维码 payload 中以 querystring 形式传输，v1 约束为 URL-safe 字符串
    nonce=st.from_regex(r"[A-Za-z0-9_-]{1,64}", fullmatch=True),
)
def test_property_2_virtual_voucher_entitlement_shape(owner_id: str, entitlement_id: str, voucher_code: str, ts: int, nonce: str):
    sign = sign_payload(secret=_SECRET, entitlement_id=entitlement_id, voucher_code=voucher_code, ts=ts, nonce=nonce)
    payload = build_payload_text(entitlement_id=entitlement_id, voucher_code=voucher_code, ts=ts, nonce=nonce, sign=sign)

    # 双形态存在
    validate_entitlement_shape(EntitlementShape(owner_id=owner_id, qr_code=payload, voucher_code=voucher_code))

    # payload 可验签（以 ts 自身作为 now_ts，保证在有效期内）
    res = verify_payload_text(secret=_SECRET, payload_text=payload, now_ts=ts)
    assert res.ok is True
    assert res.error_code is None


def test_qr_payload_expired_returns_expected_error_code():
    entitlement_id = "e1"
    voucher_code = "0123456789ABCDEF"
    ts = 1_000_000
    nonce = "n1"
    sign = sign_payload(secret=_SECRET, entitlement_id=entitlement_id, voucher_code=voucher_code, ts=ts, nonce=nonce)
    payload = build_payload_text(entitlement_id=entitlement_id, voucher_code=voucher_code, ts=ts, nonce=nonce, sign=sign)

    # 10分钟+1秒
    res = verify_payload_text(secret=_SECRET, payload_text=payload, now_ts=ts + 10 * 60 + 1)
    assert res.ok is False
    assert res.error_code == "QR_SIGN_EXPIRED"

