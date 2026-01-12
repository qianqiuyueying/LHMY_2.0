"""Admin AI 能力平台（v2：Provider/Strategy/绑定）。

规格来源（单一真相来源）：
- specs/health-services-platform/ai-gateway-v2.md
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from app.models.ai_provider import AiProvider
from app.models.ai_strategy import AiStrategy
from app.models.audit_log import AuditLog
from app.models.enums import AiProviderType, AuditAction, AuditActorType, CommonEnabledStatus
from app.services.ai.factory import create_adapter
from app.services.ai.types import AiCallContext, AiProviderSnapshot, AiStrategySnapshot
from app.services.idempotency import IdemActorType, IdempotencyCachedResult, IdempotencyService
from app.utils.redis_client import get_redis
from app.utils.db import get_session_factory
from app.utils.response import fail, ok
from app.api.v1.deps import require_admin
from app.services.rbac import ActorContext
from app.utils.datetime_iso import iso as _iso
from app.utils.settings import settings

router = APIRouter(tags=["admin-ai"])
_OPERATION_POST_AI_PROVIDER = "ADMIN_POST_AI_PROVIDER"
_OPERATION_PUT_AI_PROVIDER = "ADMIN_PUT_AI_PROVIDER"
_OPERATION_TEST_AI_PROVIDER = "ADMIN_TEST_AI_PROVIDER"
_OPERATION_POST_AI_STRATEGY = "ADMIN_POST_AI_STRATEGY"
_OPERATION_PUT_AI_STRATEGY = "ADMIN_PUT_AI_STRATEGY"
_OPERATION_BIND_AI_STRATEGY_PROVIDER = "ADMIN_BIND_AI_STRATEGY_PROVIDER"


_TZ_BEIJING = timezone(timedelta(hours=8))


def _parse_beijing_day(raw: str, *, field_name: str) -> date:
    try:
        if len(raw) != 10:
            raise ValueError("expected YYYY-MM-DD")
        return date.fromisoformat(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ARGUMENT", "message": f"{field_name} 时间格式不合法"}
        ) from exc


def _beijing_day_range_to_utc_naive(d: date) -> tuple[datetime, datetime]:
    start_bj = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    next_day = d + timedelta(days=1)
    end_bj_exclusive = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=_TZ_BEIJING)
    return (
        start_bj.astimezone(timezone.utc).replace(tzinfo=None),
        end_bj_exclusive.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _mask_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    s = str(api_key).strip()
    if len(s) <= 8:
        return "****"
    return f"{s[:3]}****{s[-4:]}"


def _safe_provider_audit_view(row: AiProvider) -> dict:
    """用于审计 before/after：禁止包含 apiKey 明文。"""
    creds = dict(row.credentials_json or {})
    api_key_masked = _mask_api_key(str(creds.get("api_key") or creds.get("apiKey") or ""))
    # 永远不返回明文
    safe_creds = {k: ("****" if k in ("api_key", "apiKey") else v) for k, v in creds.items() if k != "api_key"}
    # 上面 safe_creds 仍可能包含 app_id（非敏感）；api_key 只用 masked 表达
    return {
        "id": str(row.id),
        "name": str(row.name),
        "providerType": str(row.provider_type),
        "endpoint": (str(row.endpoint) if row.endpoint else None),
        "extra": dict(row.extra_json or {}),
        "status": str(row.status),
        "apiKeyMasked": api_key_masked,
        "credentialsKeys": sorted(list(creds.keys())),
    }


def _safe_strategy_audit_view(row: AiStrategy) -> dict:
    return {
        "id": str(row.id),
        "scene": str(row.scene),
        "displayName": str(row.display_name or ""),
        "providerId": (str(row.provider_id) if row.provider_id else None),
        "promptTemplate": str(row.prompt_template or ""),
        "generationConfig": dict(row.generation_config_json or {}),
        "constraints": dict(row.constraints_json or {}),
        "status": str(row.status),
    }


def _as_provider_snapshot(row: AiProvider) -> AiProviderSnapshot:
    return AiProviderSnapshot(
        id=str(row.id),
        name=str(row.name),
        provider_type=str(row.provider_type),
        credentials=dict(row.credentials_json or {}),
        endpoint=(str(row.endpoint) if row.endpoint else None),
        extra=dict(row.extra_json or {}),
    )


def _as_strategy_snapshot(scene: str, *, prompt_template: str, generation_config: dict, constraints: dict) -> AiStrategySnapshot:
    return AiStrategySnapshot(
        scene=str(scene),
        display_name="",
        provider_id=None,
        prompt_template=str(prompt_template or ""),
        generation_config=dict(generation_config or {}),
        constraints=dict(constraints or {}),
    )


def _require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key or not str(idempotency_key).strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "缺少 Idempotency-Key"})
    return str(idempotency_key).strip()


async def _idempotency_replay_if_exists(
    *,
    request: Request,
    operation: str,
    actor_type: IdemActorType,
    actor_id: str,
    idempotency_key: str,
) -> JSONResponse | None:
    idem = IdempotencyService(get_redis())
    cached = await idem.get(operation=operation, actor_type=actor_type, actor_id=actor_id, idempotency_key=idempotency_key)
    if cached is None:
        return None

    if cached.success:
        payload = ok(data=cached.data, request_id=request.state.request_id)
    else:
        err = cached.error or {"code": "INTERNAL_ERROR", "message": "服务器内部错误", "details": None}
        payload = fail(
            code=str(err.get("code", "INTERNAL_ERROR")),
            message=str(err.get("message", "服务器内部错误")),
            details=err.get("details"),
            request_id=request.state.request_id,
        )
    return JSONResponse(status_code=int(cached.status_code), content=payload)


# -----------------------------
# Admin：AI Provider/Strategy（v2）
# -----------------------------


class AdminAiProviderResp(BaseModel):
    id: str
    name: str
    providerType: str
    endpoint: str | None = None
    extra: dict
    status: str
    apiKeyMasked: str | None = None
    # credentials 的 key 列表（不返回明文）
    credentialsKeys: list[str]


class AdminAiStrategyResp(BaseModel):
    id: str
    scene: str
    displayName: str
    providerId: str | None = None
    promptTemplate: str
    generationConfig: dict
    constraints: dict
    status: str


@router.get("/admin/ai/providers")
async def admin_list_ai_providers(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
):
    _ = _admin
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (await session.scalars(select(AiProvider).order_by(AiProvider.created_at.desc()))).all()

    items: list[dict] = []
    for r in rows:
        items.append(AdminAiProviderResp(**_safe_provider_audit_view(r)).model_dump())
    return ok(data={"items": items}, request_id=request.state.request_id)


@router.get("/admin/ai/strategies")
async def admin_list_ai_strategies(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
):
    _ = _admin
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (await session.scalars(select(AiStrategy).order_by(AiStrategy.created_at.desc()))).all()

    items: list[dict] = []
    for r in rows:
        items.append(
            AdminAiStrategyResp(
                id=str(r.id),
                scene=str(r.scene),
                displayName=str(r.display_name or ""),
                providerId=(str(r.provider_id) if r.provider_id else None),
                promptTemplate=str(r.prompt_template or ""),
                generationConfig=dict(r.generation_config_json or {}),
                constraints=dict(r.constraints_json or {}),
                status=str(r.status),
            ).model_dump()
        )
    return ok(data={"items": items}, request_id=request.state.request_id)


@router.post("/admin/ai/providers")
async def admin_create_ai_provider(
    request: Request,
    body: dict[str, Any] = Body(default_factory=dict),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _admin: ActorContext = Depends(require_admin),
):
    admin_id = str(_admin.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation=_OPERATION_POST_AI_PROVIDER,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})

    name = body.get("name")
    provider_type = body.get("providerType") or body.get("provider_type")
    endpoint = body.get("endpoint")
    extra = body.get("extra")
    credentials = body.get("credentials")

    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "name 必须是 string"})
    name = name.strip()
    if not isinstance(provider_type, str) or provider_type.strip() not in {x.value for x in AiProviderType}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "providerType 不合法"})

    if endpoint is not None and not isinstance(endpoint, str):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "endpoint 必须是 string"})
    endpoint = (endpoint.strip() if isinstance(endpoint, str) and endpoint.strip() else None)

    if extra is None:
        extra = {}
    if not isinstance(extra, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "extra 必须是 JSON 对象"})

    if credentials is None:
        credentials = {}
    if not isinstance(credentials, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "credentials 必须是 JSON 对象"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        exists = (await session.scalars(select(AiProvider).where(AiProvider.name == name).limit(1))).first()
        if exists is not None:
            raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Provider name 已存在"})

        row = AiProvider(
            id=str(uuid4()),
            name=name,
            provider_type=str(provider_type.strip()),
            credentials_json=dict(credentials),
            endpoint=endpoint,
            extra_json=dict(extra),
            status=CommonEnabledStatus.ENABLED.value,
        )
        session.add(row)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.CREATE.value,
                resource_type="AI_PROVIDER",
                resource_id=str(row.id),
                summary="ADMIN 创建 AI Provider",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={
                    "requestId": request.state.request_id,
                    "after": _safe_provider_audit_view(row),
                },
            )
        )
        await session.commit()

    data = AdminAiProviderResp(**_safe_provider_audit_view(row)).model_dump()
    payload = ok(data=data, request_id=request.state.request_id)
    await IdempotencyService(get_redis()).set(
        operation=_OPERATION_POST_AI_PROVIDER,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return payload


@router.put("/admin/ai/providers/{providerId}")
async def admin_update_ai_provider(
    request: Request,
    providerId: str,
    body: dict[str, Any] = Body(default_factory=dict),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _admin: ActorContext = Depends(require_admin),
):
    admin_id = str(_admin.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation=_OPERATION_PUT_AI_PROVIDER,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(AiProvider).where(AiProvider.id == providerId).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Provider 不存在"})

        before = _safe_provider_audit_view(row)
        changed: list[str] = []
        api_key_updated = False

        # name
        if "name" in body:
            val = body.get("name")
            if val is None:
                pass
            elif not isinstance(val, str) or not val.strip():
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "name 必须是 string"})
            else:
                new_name = val.strip()
                if new_name != row.name:
                    exists = (await session.scalars(select(AiProvider).where(AiProvider.name == new_name).limit(1))).first()
                    if exists is not None and exists.id != row.id:
                        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Provider name 已存在"})
                    row.name = new_name
                    changed.append("name")

        # providerType
        if "providerType" in body or "provider_type" in body:
            val = body.get("providerType") if "providerType" in body else body.get("provider_type")
            if val is None:
                pass
            elif not isinstance(val, str) or val.strip() not in {x.value for x in AiProviderType}:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "providerType 不合法"})
            else:
                new_t = val.strip()
                if new_t != row.provider_type:
                    row.provider_type = new_t
                    changed.append("providerType")

        # endpoint
        if "endpoint" in body:
            val = body.get("endpoint")
            if val is None:
                if row.endpoint is not None:
                    row.endpoint = None
                    changed.append("endpoint")
            elif not isinstance(val, str):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "endpoint 必须是 string"})
            else:
                new_ep = val.strip() or None
                if new_ep != row.endpoint:
                    row.endpoint = new_ep
                    changed.append("endpoint")

        # extra
        if "extra" in body:
            val = body.get("extra")
            if val is None:
                pass
            elif not isinstance(val, dict):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "extra 必须是 JSON 对象"})
            else:
                row.extra_json = dict(val)
                changed.append("extra")

        # status
        if "status" in body:
            val = body.get("status")
            if val is None:
                pass
            elif not isinstance(val, str) or val.strip() not in {CommonEnabledStatus.ENABLED.value, CommonEnabledStatus.DISABLED.value}:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})
            else:
                new_status = val.strip()
                if new_status != row.status:
                    row.status = new_status
                    changed.append("status")

        # credentials：允许可选更新；api_key 空字符串视为“不更新”
        if "credentials" in body:
            val = body.get("credentials")
            if val is None:
                pass
            elif not isinstance(val, dict):
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "credentials 必须是 JSON 对象"})
            else:
                cur = dict(row.credentials_json or {})
                for k, v in val.items():
                    if k in ("api_key", "apiKey"):
                        if isinstance(v, str) and v.strip():
                            if v.strip() != str(cur.get(k) or ""):
                                cur[k] = v.strip()
                                api_key_updated = True
                                changed.append("apiKey")
                        # 空字符串：不更新
                        continue
                    cur[k] = v
                row.credentials_json = cur
                if "credentials" not in changed:
                    changed.append("credentials")

        if changed:
            after = _safe_provider_audit_view(row)
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.ADMIN.value,
                    actor_id=admin_id,
                    action=AuditAction.UPDATE.value,
                    resource_type="AI_PROVIDER",
                    resource_id=str(row.id),
                    summary="ADMIN 更新 AI Provider",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={
                        "requestId": request.state.request_id,
                        "changedFields": changed,
                        "apiKeyUpdated": api_key_updated,
                        "before": before,
                        "after": after,
                    },
                )
            )
        await session.commit()

    data = AdminAiProviderResp(**_safe_provider_audit_view(row)).model_dump()
    payload = ok(data=data, request_id=request.state.request_id)
    await IdempotencyService(get_redis()).set(
        operation=_OPERATION_PUT_AI_PROVIDER,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return payload


@router.post("/admin/ai/providers/{providerId}/test-connection")
async def admin_test_ai_provider_connection(
    request: Request,
    providerId: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _admin: ActorContext = Depends(require_admin),
):
    admin_id = str(_admin.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation=_OPERATION_TEST_AI_PROVIDER,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(AiProvider).where(AiProvider.id == providerId).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Provider 不存在"})
        provider = _as_provider_snapshot(row)

    adapter = create_adapter(provider)
    # 用一个最小 StrategySnapshot 做连通性探测（不代表真实业务策略）
    strategy = _as_strategy_snapshot(scene="connection_test", prompt_template="", generation_config={}, constraints={})

    started = time.perf_counter()
    try:
        r = await adapter.execute(
            provider=provider,
            strategy=strategy,
            user_input="ping",
            context=AiCallContext(user_id=admin_id, request_id=request.state.request_id),
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        data = {"ok": True, "latencyMs": latency_ms, "providerLatencyMs": r.provider_latency_ms}
        payload = ok(data=data, request_id=request.state.request_id)
        await IdempotencyService(get_redis()).set(
            operation=_OPERATION_TEST_AI_PROVIDER,
            actor_type="ADMIN",
            actor_id=admin_id,
            idempotency_key=idem_key,
            result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
        )
        return payload
    except HTTPException as exc:
        # 对外仍返回业务错误结构（不透传第三方细节）
        err = exc.detail if isinstance(exc.detail, dict) else {"code": "INTERNAL_ERROR", "message": "连接测试失败", "details": None}
        await IdempotencyService(get_redis()).set(
            operation=_OPERATION_TEST_AI_PROVIDER,
            actor_type="ADMIN",
            actor_id=admin_id,
            idempotency_key=idem_key,
            result=IdempotencyCachedResult(status_code=int(exc.status_code), success=False, data=None, error=err),
        )
        raise


@router.post("/admin/ai/strategies")
async def admin_create_ai_strategy(
    request: Request,
    body: dict[str, Any] = Body(default_factory=dict),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _admin: ActorContext = Depends(require_admin),
):
    admin_id = str(_admin.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation=_OPERATION_POST_AI_STRATEGY,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})

    scene = body.get("scene")
    display_name = body.get("displayName") if "displayName" in body else body.get("display_name")
    prompt_template = body.get("promptTemplate") if "promptTemplate" in body else body.get("prompt_template")
    generation_config = body.get("generationConfig") if "generationConfig" in body else body.get("generation_config")
    constraints = body.get("constraints")
    provider_id = body.get("providerId") if "providerId" in body else body.get("provider_id")

    if not isinstance(scene, str) or not scene.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "scene 必须是 string"})
    scene = scene.strip()
    if display_name is None:
        display_name = ""
    if not isinstance(display_name, str):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "displayName 必须是 string"})
    if prompt_template is None:
        prompt_template = ""
    if not isinstance(prompt_template, str):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "promptTemplate 必须是 string"})

    if generation_config is None:
        generation_config = {}
    if not isinstance(generation_config, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "generationConfig 必须是 JSON 对象"})
    if constraints is None:
        constraints = {}
    if not isinstance(constraints, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "constraints 必须是 JSON 对象"})
    if provider_id is not None and not isinstance(provider_id, str):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "providerId 必须是 string"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        exists = (await session.scalars(select(AiStrategy).where(AiStrategy.scene == scene).limit(1))).first()
        if exists is not None:
            raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "scene 已存在"})

        # 可选：校验 providerId 存在（若传入）
        if provider_id and provider_id.strip():
            pv = (await session.scalars(select(AiProvider).where(AiProvider.id == provider_id.strip()).limit(1))).first()
            if pv is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "providerId 不存在"})

        row = AiStrategy(
            id=str(uuid4()),
            scene=scene,
            display_name=str(display_name),
            provider_id=(provider_id.strip() if isinstance(provider_id, str) and provider_id.strip() else None),
            prompt_template=str(prompt_template),
            generation_config_json=dict(generation_config),
            constraints_json=dict(constraints),
            status=CommonEnabledStatus.ENABLED.value,
        )
        session.add(row)
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.CREATE.value,
                resource_type="AI_STRATEGY",
                resource_id=str(row.id),
                summary="ADMIN 创建 AI Strategy",
                ip=getattr(getattr(request, "client", None), "host", None),
                user_agent=request.headers.get("User-Agent"),
                metadata_json={"requestId": request.state.request_id, "after": _safe_strategy_audit_view(row)},
            )
        )
        await session.commit()

    data = AdminAiStrategyResp(**_safe_strategy_audit_view(row)).model_dump()
    payload = ok(data=data, request_id=request.state.request_id)
    await IdempotencyService(get_redis()).set(
        operation=_OPERATION_POST_AI_STRATEGY,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return payload


@router.put("/admin/ai/strategies/{strategyId}")
async def admin_update_ai_strategy(
    request: Request,
    strategyId: str,
    body: dict[str, Any] = Body(default_factory=dict),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _admin: ActorContext = Depends(require_admin),
):
    admin_id = str(_admin.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation=_OPERATION_PUT_AI_STRATEGY,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        row = (await session.scalars(select(AiStrategy).where(AiStrategy.id == strategyId).limit(1))).first()
        if row is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Strategy 不存在"})
        before = _safe_strategy_audit_view(row)
        changed: list[str] = []

        if "displayName" in body or "display_name" in body:
            val = body.get("displayName") if "displayName" in body else body.get("display_name")
            if val is not None:
                if not isinstance(val, str):
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "displayName 必须是 string"})
                if val != str(row.display_name or ""):
                    row.display_name = val
                    changed.append("displayName")

        if "promptTemplate" in body or "prompt_template" in body:
            val = body.get("promptTemplate") if "promptTemplate" in body else body.get("prompt_template")
            if val is not None:
                if not isinstance(val, str):
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "promptTemplate 必须是 string"})
                if val != str(row.prompt_template or ""):
                    row.prompt_template = val
                    changed.append("promptTemplate")

        if "generationConfig" in body or "generation_config" in body:
            val = body.get("generationConfig") if "generationConfig" in body else body.get("generation_config")
            if val is not None:
                if not isinstance(val, dict):
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "generationConfig 必须是 JSON 对象"})
                row.generation_config_json = dict(val)
                changed.append("generationConfig")

        if "constraints" in body:
            val = body.get("constraints")
            if val is not None:
                if not isinstance(val, dict):
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "constraints 必须是 JSON 对象"})
                row.constraints_json = dict(val)
                changed.append("constraints")

        if "status" in body:
            val = body.get("status")
            if val is not None:
                if not isinstance(val, str) or val.strip() not in {CommonEnabledStatus.ENABLED.value, CommonEnabledStatus.DISABLED.value}:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "status 不合法"})
                new_status = val.strip()
                if new_status != row.status:
                    row.status = new_status
                    changed.append("status")

        # providerId 只允许通过 bind 接口更新（避免混在普通编辑里造成误操作）

        if changed:
            after = _safe_strategy_audit_view(row)
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.ADMIN.value,
                    actor_id=admin_id,
                    action=AuditAction.UPDATE.value,
                    resource_type="AI_STRATEGY",
                    resource_id=str(row.id),
                    summary="ADMIN 更新 AI Strategy",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={"requestId": request.state.request_id, "changedFields": changed, "before": before, "after": after},
                )
            )
        await session.commit()

    data = AdminAiStrategyResp(**_safe_strategy_audit_view(row)).model_dump()
    payload = ok(data=data, request_id=request.state.request_id)
    await IdempotencyService(get_redis()).set(
        operation=_OPERATION_PUT_AI_STRATEGY,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return payload


@router.post("/admin/ai/strategies/{strategyId}/bind-provider")
async def admin_bind_ai_strategy_provider(
    request: Request,
    strategyId: str,
    body: dict[str, Any] = Body(default_factory=dict),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _admin: ActorContext = Depends(require_admin),
):
    # 说明：开发/测试阶段允许快速联调，不要求 admin 先绑手机（2FA）。
    admin_id = str(_admin.sub)
    idem_key = _require_idempotency_key(idempotency_key)
    replay = await _idempotency_replay_if_exists(
        request=request,
        operation=_OPERATION_BIND_AI_STRATEGY_PROVIDER,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
    )
    if replay is not None:
        return replay
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "body 必须是 JSON 对象"})
    provider_id = body.get("providerId") if "providerId" in body else body.get("provider_id")
    if provider_id is not None and not isinstance(provider_id, str):
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "providerId 必须是 string"})
    provider_id = (provider_id.strip() if isinstance(provider_id, str) and provider_id.strip() else None)

    session_factory = get_session_factory()
    async with session_factory() as session:
        st = (await session.scalars(select(AiStrategy).where(AiStrategy.id == strategyId).limit(1))).first()
        if st is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Strategy 不存在"})
        before = _safe_strategy_audit_view(st)

        if provider_id is not None:
            pv = (await session.scalars(select(AiProvider).where(AiProvider.id == provider_id).limit(1))).first()
            if pv is None:
                raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "providerId 不存在"})

        if provider_id != (str(st.provider_id) if st.provider_id else None):
            st.provider_id = provider_id
            after = _safe_strategy_audit_view(st)
            session.add(
                AuditLog(
                    id=str(uuid4()),
                    actor_type=AuditActorType.ADMIN.value,
                    actor_id=admin_id,
                    action=AuditAction.UPDATE.value,
                    resource_type="AI_STRATEGY_BINDING",
                    resource_id=str(st.id),
                    summary="ADMIN 绑定 Strategy Provider",
                    ip=getattr(getattr(request, "client", None), "host", None),
                    user_agent=request.headers.get("User-Agent"),
                    metadata_json={"requestId": request.state.request_id, "before": before, "after": after},
                )
            )
        await session.commit()

    data = AdminAiStrategyResp(**_safe_strategy_audit_view(st)).model_dump()
    payload = ok(data=data, request_id=request.state.request_id)
    await IdempotencyService(get_redis()).set(
        operation=_OPERATION_BIND_AI_STRATEGY_PROVIDER,
        actor_type="ADMIN",
        actor_id=admin_id,
        idempotency_key=idem_key,
        result=IdempotencyCachedResult(status_code=200, success=True, data=data, error=None),
    )
    return payload


class AdminAiDevResetBody(BaseModel):
    resetAudit: bool = True
    resetChatAudits: bool = False


@router.post("/admin/ai/dev/reset")
async def admin_dev_reset_ai_config(
    request: Request,
    body: AdminAiDevResetBody,
    _admin: ActorContext = Depends(require_admin),
):
    # 仅开发/测试允许：避免生产误删
    if str(getattr(settings, "app_env", "") or "").strip().lower() == "production":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "生产环境禁止清空 AI 配置"})

    session_factory = get_session_factory()
    async with session_factory() as session:
        # 先删 Strategy 再删 Provider（避免外键/逻辑依赖；当前无 FK 也按此顺序更安全）
        await session.execute(delete(AiStrategy))
        await session.execute(delete(AiProvider))

        if body.resetAudit:
            # 清理配置类审计（不含对话审计）
            await session.execute(
                delete(AuditLog).where(
                    AuditLog.resource_type.in_(["AI_PROVIDER", "AI_STRATEGY", "AI_STRATEGY_BINDING", "AI_MIGRATION"])
                )
            )
        if body.resetChatAudits:
            await session.execute(delete(AuditLog).where(AuditLog.resource_type == "AI_CHAT"))

        await session.commit()

    return ok(data={"reset": True}, request_id=request.state.request_id)


# -----------------------------
# Admin：AI 调用审计日志（阶段11）
# -----------------------------


@router.get("/admin/ai/audit-logs")
async def admin_list_ai_audit_logs(
    request: Request,
    _admin: ActorContext = Depends(require_admin),
    userId: str | None = None,
    resultStatus: Literal["success", "fail"] | None = None,
    provider: str | None = None,
    model: str | None = None,
    scene: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    _ = _admin

    page = max(1, int(page))
    page_size = max(1, min(100, int(pageSize)))

    # v1：基于 audit_logs 过滤 resourceType="AI_CHAT" 聚合生成（不存储对话内容）
    stmt = select(AuditLog).where(AuditLog.resource_type == "AI_CHAT")

    if userId and userId.strip():
        stmt = stmt.where(AuditLog.actor_id == userId.strip())

    def _json_str(field: str):
        # mysql JSON：json_extract + json_unquote
        return func.json_unquote(func.json_extract(AuditLog.metadata_json, f"$.{field}"))

    if resultStatus:
        stmt = stmt.where(_json_str("resultStatus") == str(resultStatus))
    if provider and provider.strip():
        stmt = stmt.where(_json_str("provider") == provider.strip())
    if model and model.strip():
        stmt = stmt.where(_json_str("model") == model.strip())
    if scene and scene.strip():
        stmt = stmt.where(_json_str("scene") == scene.strip())

    # Spec (Admin): dateFrom/dateTo are Beijing natural days (YYYY-MM-DD)
    if dateFrom:
        d_from = _parse_beijing_day(str(dateFrom), field_name="dateFrom")
        start_utc, _end_exclusive = _beijing_day_range_to_utc_naive(d_from)
        stmt = stmt.where(AuditLog.created_at >= start_utc)
    if dateTo:
        d_to = _parse_beijing_day(str(dateTo), field_name="dateTo")
        _start_utc, end_exclusive = _beijing_day_range_to_utc_naive(d_to)
        stmt = stmt.where(AuditLog.created_at < end_exclusive)

    stmt = stmt.order_by(AuditLog.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())

    session_factory = get_session_factory()
    async with session_factory() as session:
        total = int((await session.execute(count_stmt)).scalar() or 0)
        logs = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()

    items: list[dict] = []
    for x in logs:
        meta = x.metadata_json or {}
        items.append(
            {
                "userId": str(meta.get("userId") or x.actor_id),
                "timestamp": _iso(x.created_at),
                "provider": str(meta.get("provider") or ""),
                "model": str(meta.get("model") or ""),
                "scene": str(meta.get("scene") or ""),
                "latencyMs": int(meta.get("latencyMs") or 0),
                "resultStatus": str(meta.get("resultStatus") or ""),
                "errorCode": (str(meta.get("errorCode")) if meta.get("errorCode") else None),
                "configVersion": (str(meta.get("configVersion")) if meta.get("configVersion") else None),
            }
        )

    return ok(
        data={"items": items, "page": page, "pageSize": page_size, "total": total},
        request_id=request.state.request_id,
    )
