"""微信 code 换取 openid/unionid（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> `POST /api/v1/mini-program/auth/login` 实现口径

实现要点（按规格）：
- unionid 来源：`https://api.weixin.qq.com/sns/jscode2session`
- mock：
  - `code=mock:unionid:xxx` -> unionid=xxx
  - `code=mock:openid:xxx` -> openid=xxx（无 unionid）
- 错误边界：
  - INVALID_ARGUMENT(400)：mock 格式不匹配
  - UNAUTHENTICATED(401)：微信接口返回错误（code 过期/已使用等）

注意：
- 微信接口必返 openid，但 unionid 不保证拿到。
- v1：新增 `users.openid` 字段后，openid 将落库到 `users.openid`，unionid（如有）落库到 `users.unionid`。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from app.utils.settings import settings


_MOCK_UNIONID_RE = re.compile(r"^mock:unionid:(?P<id>.+)$")
_MOCK_OPENID_RE = re.compile(r"^mock:openid:(?P<id>.+)$")


@dataclass(frozen=True)
class WechatCodeExchangeResult:
    openid: str
    unionid: str | None


async def exchange_wechat_code(*, code: str) -> WechatCodeExchangeResult:
    # mock 口径（用于本地/测试）
    if code.startswith("mock:"):
        m1 = _MOCK_UNIONID_RE.match(code)
        if m1:
            value = m1.group("id")
            return WechatCodeExchangeResult(openid=value, unionid=value)
        m2 = _MOCK_OPENID_RE.match(code)
        if m2:
            value = m2.group("id")
            return WechatCodeExchangeResult(openid=value, unionid=None)
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "code 格式不合法"})

    # 可选：第三方代换服务（若配置）
    if settings.wechat_code_exchange_service_url.strip():
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    settings.wechat_code_exchange_service_url.strip(),
                    json={"code": code},
                )
                data = resp.json()
        except Exception as exc:  # noqa: BLE001 - 统一按未认证处理
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "微信登录失败"}) from exc

        if not isinstance(data, dict) or not data.get("openid"):
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "微信登录失败"})
        return WechatCodeExchangeResult(openid=str(data["openid"]), unionid=str(data["unionid"]) if data.get("unionid") else None)

    # 直连微信接口
    if not settings.wechat_appid.strip() or not settings.wechat_secret.strip():
        # 配置缺失属于服务端问题
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": "微信登录配置缺失"})

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.wechat_appid.strip(),
        "secret": settings.wechat_secret.strip(),
        "js_code": code,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "微信登录失败"}) from exc

    # 微信失败：通常返回 {"errcode":..., "errmsg":...}
    if not isinstance(data, dict) or data.get("errcode"):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "微信登录失败", "details": data})

    openid = data.get("openid")
    if not openid:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "微信登录失败"})

    unionid = data.get("unionid")
    return WechatCodeExchangeResult(openid=str(openid), unionid=str(unionid) if unionid else None)

