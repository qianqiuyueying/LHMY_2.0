"""集成测试：requestId 一致性（TASK-P0-009）。

规格依据（单一真相来源）：
- specs-prod/admin/observability.md#1.1（requestId 必须贯穿响应与日志/审计）
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(os.getenv("RUN_INTEGRATION_TESTS") != "1", reason="integration tests disabled")


def test_request_id_header_equals_envelope_request_id_on_success():
    client = TestClient(app)
    rid = "it-rid-success-001"
    r = client.get("/api/v1/health", headers={"X-Request-Id": rid})
    assert r.status_code == 200
    assert r.headers.get("X-Request-Id") == rid
    body = r.json()
    assert body.get("success") is True
    assert body.get("requestId") == rid


def test_request_id_header_equals_envelope_request_id_on_error():
    client = TestClient(app)
    rid = "it-rid-error-001"
    r = client.get("/api/v1/admin/users", headers={"X-Request-Id": rid})  # unauthenticated -> 401
    assert r.status_code == 401
    assert r.headers.get("X-Request-Id") == rid
    body = r.json()
    assert body.get("success") is False
    assert body.get("requestId") == rid


