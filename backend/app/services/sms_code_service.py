"""短信验证码服务（v1 最小可执行口径）。

规格来源：
- specs/health-services-platform/design.md -> 「短信验证码（H5 购买 + 小程序绑定手机号，v1 最小可执行口径）」
- specs/health-services-platform/design.md -> 附录 A：错误码
  - INVALID_PHONE / RATE_LIMITED / SMS_CODE_INVALID / SMS_CODE_EXPIRED
- specs/health-services-platform/tasks.md -> 阶段3-14

说明：
- v1 不接入真实短信供应商；仅生成并存储验证码，同时输出日志便于联调/验收。
- Redis 是裁决来源：验证码、发送频控、每日次数、失败锁定均由 Redis key 决定。
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


_CN_PHONE_RE = re.compile(r"^1\d{10}$")


def _validate_phone(phone: str) -> None:
    if not isinstance(phone, str) or not _CN_PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail={"code": "INVALID_PHONE", "message": "手机号不合法"})


@dataclass(frozen=True)
class SmsCodeRequestResult:
    sent: bool
    expires_in_seconds: int
    resend_after_seconds: int


class SmsCodeService:
    """短信验证码服务。

    场景 scene（严格按规格）：
    - H5_BUY：H5 购买/登录前置手机号校验
    - MP_BIND_PHONE：小程序绑定手机号并触发合并
    """

    # 规格默认值（v1 验收口径）
    _CODE_TTL_SECONDS = 5 * 60
    _RESEND_COOLDOWN_SECONDS = 60
    _DAILY_LIMIT = 20
    _MAX_VERIFY_FAILS = 10
    _FAIL_LOCK_SECONDS = 30 * 60

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _now() -> datetime:
        return datetime.now(tz=UTC)

    @staticmethod
    def _today_key() -> str:
        # 以 UTC 的自然日作为“每日上限”口径，避免环境时区不一致导致验收口径漂移。
        return SmsCodeService._now().strftime("%Y%m%d")

    @staticmethod
    def _seconds_until_next_utc_day() -> int:
        now = SmsCodeService._now()
        next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, int((next_day - now).total_seconds()))

    @staticmethod
    def _code_key(scene: str, phone: str) -> str:
        return f"sms:code:{scene}:{phone}"

    @staticmethod
    def _cooldown_key(scene: str, phone: str) -> str:
        return f"sms:cooldown:{scene}:{phone}"

    @staticmethod
    def _daily_key(scene: str, phone: str) -> str:
        return f"sms:daily:{SmsCodeService._today_key()}:{scene}:{phone}"

    @staticmethod
    def _fail_key(scene: str, phone: str) -> str:
        return f"sms:fail:{scene}:{phone}"

    @staticmethod
    def _lock_key(scene: str, phone: str) -> str:
        return f"sms:lock:{scene}:{phone}"

    async def request_code(self, *, phone: str, scene: str) -> SmsCodeRequestResult:
        """生成并存储验证码。

        Errors（按规格）：
        - INVALID_PHONE(400)
        - RATE_LIMITED(429) 频控/每日上限/锁定均归为 RATE_LIMITED
        """

        _validate_phone(phone)

        # 锁定期间直接当作限流处理（v1 最小可执行口径）
        if await self._redis.exists(self._lock_key(scene, phone)):
            raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "请求过于频繁"})

        # 同手机号 60s 间隔
        cooldown_key = self._cooldown_key(scene, phone)
        if await self._redis.exists(cooldown_key):
            raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "请求过于频繁"})

        # 每日 20 次上限（UTC 自然日）
        daily_key = self._daily_key(scene, phone)
        daily_count = await self._redis.incr(daily_key)
        if daily_count == 1:
            await self._redis.expire(daily_key, self._seconds_until_next_utc_day())
        if daily_count > self._DAILY_LIMIT:
            raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "请求过于频繁"})

        # 生成 6 位数字码
        sms_code = f"{random.randint(0, 999999):06d}"

        # 存储验证码（5 分钟）
        await self._redis.set(self._code_key(scene, phone), sms_code, ex=self._CODE_TTL_SECONDS)

        # 设置冷却（60 秒）
        await self._redis.set(cooldown_key, "1", ex=self._RESEND_COOLDOWN_SECONDS)

        # v1：不对接供应商，仅日志输出，便于联调
        logger.info("已生成短信验证码（v1 mock，不实际发送）：scene=%s phone=%s code=%s", scene, phone, sms_code)

        return SmsCodeRequestResult(
            sent=True,
            expires_in_seconds=self._CODE_TTL_SECONDS,
            resend_after_seconds=self._RESEND_COOLDOWN_SECONDS,
        )

    async def verify_code(self, *, phone: str, scene: str, sms_code: str) -> None:
        """校验短信验证码（失败锁定）。

        Errors（按规格）：
        - SMS_CODE_INVALID(400)
        - SMS_CODE_EXPIRED(400)
        - RATE_LIMITED(429)（失败锁定窗口内）
        """

        _validate_phone(phone)

        if await self._redis.exists(self._lock_key(scene, phone)):
            raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED", "message": "请求过于频繁"})

        code_key = self._code_key(scene, phone)
        stored = await self._redis.get(code_key)
        if stored is None:
            raise HTTPException(status_code=400, detail={"code": "SMS_CODE_EXPIRED", "message": "验证码已过期"})

        stored_code = stored.decode("utf-8") if isinstance(stored, (bytes, bytearray)) else str(stored)
        if stored_code != sms_code:
            fail_key = self._fail_key(scene, phone)
            fail_count = await self._redis.incr(fail_key)
            # 失败次数窗口：30 分钟（达到阈值后锁定；最小可执行口径）
            if fail_count == 1:
                await self._redis.expire(fail_key, self._FAIL_LOCK_SECONDS)
            if fail_count >= self._MAX_VERIFY_FAILS:
                await self._redis.set(self._lock_key(scene, phone), "1", ex=self._FAIL_LOCK_SECONDS)
            raise HTTPException(status_code=400, detail={"code": "SMS_CODE_INVALID", "message": "验证码错误"})

        # 校验成功：删除验证码并清理失败计数
        await self._redis.delete(code_key)
        await self._redis.delete(self._fail_key(scene, phone))
