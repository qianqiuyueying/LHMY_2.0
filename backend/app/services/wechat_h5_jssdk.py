"""微信 H5（公众号）JS-SDK 签名支持（v1）。

用途：
- 为 H5（微信内）提供 wx.config 所需参数，使 wx-open-launch-weapp 可用。

说明：
- access_token 与 jsapi_ticket 都有频控，必须缓存（Redis）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.utils.redis_client import get_redis
from app.utils.settings import settings


_WX_API_BASE = "https://api.weixin.qq.com"


def _sha1_hex(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()  # noqa: S324


async def _get_cached_json(key: str) -> dict | None:
    redis = get_redis()
    raw = await redis.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw))
    except Exception:  # noqa: BLE001
        return None


async def _set_cached_json(key: str, value: dict, ttl_seconds: int) -> None:
    redis = get_redis()
    await redis.set(key, json.dumps(value, ensure_ascii=False, separators=(",", ":")), ex=int(ttl_seconds))


async def _fetch_access_token() -> tuple[str, int]:
    appid = (settings.wechat_h5_appid or "").strip()
    secret = (settings.wechat_h5_secret or "").strip()
    if not (appid and secret):
        raise RuntimeError("WECHAT_H5_APPID/WECHAT_H5_SECRET 未配置")

    key = f"wx:h5:access_token:{appid}"
    cached = await _get_cached_json(key)
    if cached and str(cached.get("access_token") or "").strip():
        return (str(cached["access_token"]), int(cached.get("expires_in") or 0))

    url = f"{_WX_API_BASE}/cgi-bin/token"
    params = {"grant_type": "client_credential", "appid": appid, "secret": secret}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params)
        data = r.json() if r.content else {}

    token = str(data.get("access_token") or "").strip()
    expires_in = int(data.get("expires_in") or 0)
    if not token or expires_in <= 0:
        err = str(data.get("errmsg") or "获取 access_token 失败")
        raise RuntimeError(err)

    # 预留 200 秒缓冲，避免临界过期
    ttl = max(60, expires_in - 200)
    await _set_cached_json(key, {"access_token": token, "expires_in": expires_in}, ttl_seconds=ttl)
    return (token, expires_in)


async def _fetch_jsapi_ticket() -> tuple[str, int]:
    appid = (settings.wechat_h5_appid or "").strip()
    if not appid:
        raise RuntimeError("WECHAT_H5_APPID 未配置")

    key = f"wx:h5:jsapi_ticket:{appid}"
    cached = await _get_cached_json(key)
    if cached and str(cached.get("ticket") or "").strip():
        return (str(cached["ticket"]), int(cached.get("expires_in") or 0))

    access_token, _exp = await _fetch_access_token()
    url = f"{_WX_API_BASE}/cgi-bin/ticket/getticket"
    params = {"access_token": access_token, "type": "jsapi"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params)
        data = r.json() if r.content else {}

    if int(data.get("errcode") or 0) != 0:
        err = str(data.get("errmsg") or "获取 jsapi_ticket 失败")
        raise RuntimeError(err)

    ticket = str(data.get("ticket") or "").strip()
    expires_in = int(data.get("expires_in") or 0)
    if not ticket or expires_in <= 0:
        raise RuntimeError("获取 jsapi_ticket 失败")

    ttl = max(60, expires_in - 200)
    await _set_cached_json(key, {"ticket": ticket, "expires_in": expires_in}, ttl_seconds=ttl)
    return (ticket, expires_in)


@dataclass(frozen=True)
class WechatJssdkConfig:
    appId: str
    timestamp: int
    nonceStr: str
    signature: str


async def build_wechat_jssdk_config(*, url: str) -> WechatJssdkConfig:
    """生成 wx.config 所需参数。

    参数：
    - url：当前页面 URL（不含 hash）
    """

    appid = (settings.wechat_h5_appid or "").strip()
    if not appid:
        raise RuntimeError("WECHAT_H5_APPID 未配置")

    u = str(url or "").strip()
    if not u:
        raise ValueError("url 不能为空")

    # 微信签名要求：url 不包含 # 后的部分
    if "#" in u:
        u = u.split("#", 1)[0]

    ticket, _exp = await _fetch_jsapi_ticket()
    nonce = uuid4().hex
    ts = int(datetime.now(tz=UTC).timestamp())

    # 签名串：按文档字段名小写，且用 & 连接
    plain = f"jsapi_ticket={ticket}&noncestr={nonce}&timestamp={ts}&url={u}"
    sig = _sha1_hex(plain)
    return WechatJssdkConfig(appId=appid, timestamp=ts, nonceStr=nonce, signature=sig)


