"""基础设施阶段最小测试：健康检查与统一响应体。"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_response_shape():
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200

    body = resp.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["data"] == {"status": "ok"}
    assert isinstance(body["requestId"], str)
    assert body["requestId"]
