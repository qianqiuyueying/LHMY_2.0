"""幂等性支持（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> API 通用约定（v1）-> 幂等（24h，同一用户同一 key 返回首次结果）
- specs/health-services-platform/tasks.md -> 阶段4-24.2 / 25.1（以及后续创建预约/核销/转赠等）

实现口径（v1）：
- 同一 actor（USER/ADMIN 等）在 24h 内对同一 operation + Idempotency-Key 的重复请求：
  - 返回首次结果（success/data 或 error/code/message/details）
  - 不重复产生副作用（不重复写库）
- requestId 属于“本次请求”，因此重放时返回缓存的 data/error，但 requestId 仍取当前请求的 request.state.request_id。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Optional


IdemActorType = Literal["USER", "ADMIN", "DEALER", "PROVIDER", "PROVIDER_STAFF"]


@dataclass(frozen=True)
class IdempotencyCachedResult:
    status_code: int
    success: bool
    data: Any | None
    error: dict[str, Any] | None


class IdempotencyService:
    def __init__(self, redis):
        self._redis = redis

    @staticmethod
    def _key(*, operation: str, actor_type: IdemActorType, actor_id: str, idempotency_key: str) -> str:
        return f"idem:{operation}:{actor_type}:{actor_id}:{idempotency_key}"

    async def get(
        self,
        *,
        operation: str,
        actor_type: IdemActorType,
        actor_id: str,
        idempotency_key: str,
    ) -> Optional[IdempotencyCachedResult]:
        key = self._key(operation=operation, actor_type=actor_type, actor_id=actor_id, idempotency_key=idempotency_key)
        raw = await self._redis.get(key)
        if raw is None:
            return None

        try:
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw))
        except Exception:  # noqa: BLE001
            # 缓存损坏：当作不存在，避免阻断主流程
            return None

        try:
            return IdempotencyCachedResult(
                status_code=int(payload["status_code"]),
                success=bool(payload["success"]),
                data=payload.get("data"),
                error=payload.get("error"),
            )
        except Exception:  # noqa: BLE001
            return None

    async def set(
        self,
        *,
        operation: str,
        actor_type: IdemActorType,
        actor_id: str,
        idempotency_key: str,
        result: IdempotencyCachedResult,
        ttl_seconds: int = 24 * 60 * 60,
    ) -> None:
        key = self._key(operation=operation, actor_type=actor_type, actor_id=actor_id, idempotency_key=idempotency_key)
        value = {
            "status_code": result.status_code,
            "success": result.success,
            "data": result.data,
            "error": result.error,
        }
        await self._redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)

