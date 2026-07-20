"""问答接口集成测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.mark.skip(reason="需要真实模型和依赖")
def test_chat_without_session(client):
    """测试无会话直接问答。"""
    response = client.post(
        "/api/chat",
        json={"question": "什么是 RAG?"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "answer" in data
    assert "session_id" in data


@pytest.mark.skip(reason="需要真实模型和依赖")
def test_health_check(client):
    """测试健康检查。"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ok"
