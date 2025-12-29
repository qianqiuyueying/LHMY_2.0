"""单元测试：生产环境启动门禁（v1 最小）。

规格来源：
- specs/功能实现/admin/tasks.md -> F. 生产就绪门禁（Go-Live Gates）可验证化（补充可回归证据）
- README.md -> “APP_ENV=production 时缺少关键配置会拒绝启动”

目的：
- 确保 production 下默认/空密钥会被阻断（避免带默认密钥上线）
- 确保配置齐全时门禁不会误伤（可正常启动）
"""

from __future__ import annotations

import pytest

from app.main import _validate_production_settings, settings


def _snapshot_settings(keys: list[str]) -> dict[str, object]:
    return {k: getattr(settings, k) for k in keys}


def _restore_settings(snapshot: dict[str, object]) -> None:
    for k, v in snapshot.items():
        setattr(settings, k, v)


def test_production_startup_gate_rejects_default_or_empty_secrets():
    keys = [
        "app_env",
        "jwt_secret",
        "jwt_secret_admin",
        "jwt_secret_provider",
        "jwt_secret_dealer",
        "entitlement_qr_sign_secret",
        "dealer_sign_secret",
        "wechat_appid",
        "wechat_secret",
        "wechat_pay_mch_id",
        "wechat_pay_appid",
        "wechat_pay_mch_cert_serial",
        "wechat_pay_mch_private_key_pem_or_path",
        "wechat_pay_notify_url",
    ]
    snap = _snapshot_settings(keys)
    try:
        # 先放行其它必填项，只故意保留一个“默认值”触发门禁
        settings.app_env = "production"
        settings.jwt_secret = "not_default_jwt_secret"
        settings.jwt_secret_provider = "not_default_jwt_secret_provider"
        settings.jwt_secret_dealer = "not_default_jwt_secret_dealer"
        settings.entitlement_qr_sign_secret = "not_default_entitlement_qr_sign_secret"
        settings.dealer_sign_secret = "not_default_dealer_sign_secret"
        settings.wechat_appid = "wx_dummy"
        settings.wechat_secret = "wechat_secret_dummy"
        settings.wechat_pay_mch_id = "mch_dummy"
        settings.wechat_pay_appid = "wx_pay_appid_dummy"
        settings.wechat_pay_mch_cert_serial = "serial_dummy"
        settings.wechat_pay_mch_private_key_pem_or_path = "pem_dummy"
        settings.wechat_pay_notify_url = "https://example.com/api/v1/payments/wechat/notify"

        # 故意不改：仍为默认值（不安全） -> 应抛错
        settings.jwt_secret_admin = "change_me_jwt_secret_admin"

        with pytest.raises(RuntimeError, match="missing or insecure config: JWT_SECRET_ADMIN"):
            _validate_production_settings()
    finally:
        _restore_settings(snap)


def test_production_startup_gate_allows_when_required_settings_present():
    keys = [
        "app_env",
        "jwt_secret",
        "jwt_secret_admin",
        "jwt_secret_provider",
        "jwt_secret_dealer",
        "entitlement_qr_sign_secret",
        "dealer_sign_secret",
        "wechat_appid",
        "wechat_secret",
        "wechat_pay_mch_id",
        "wechat_pay_appid",
        "wechat_pay_mch_cert_serial",
        "wechat_pay_mch_private_key_pem_or_path",
        "wechat_pay_notify_url",
    ]
    snap = _snapshot_settings(keys)
    try:
        settings.app_env = "production"
        settings.jwt_secret = "not_default_jwt_secret"
        settings.jwt_secret_admin = "not_default_jwt_secret_admin"
        settings.jwt_secret_provider = "not_default_jwt_secret_provider"
        settings.jwt_secret_dealer = "not_default_jwt_secret_dealer"
        settings.entitlement_qr_sign_secret = "not_default_entitlement_qr_sign_secret"
        settings.dealer_sign_secret = "not_default_dealer_sign_secret"
        settings.wechat_appid = "wx_dummy"
        settings.wechat_secret = "wechat_secret_dummy"
        settings.wechat_pay_mch_id = "mch_dummy"
        settings.wechat_pay_appid = "wx_pay_appid_dummy"
        settings.wechat_pay_mch_cert_serial = "serial_dummy"
        settings.wechat_pay_mch_private_key_pem_or_path = "pem_dummy"
        settings.wechat_pay_notify_url = "https://example.com/api/v1/payments/wechat/notify"

        _validate_production_settings()  # no raise
    finally:
        _restore_settings(snap)

