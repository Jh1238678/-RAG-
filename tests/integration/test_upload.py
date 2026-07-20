"""上传接口集成测试。

注意：需要启动应用和真实模型，标记为慢测试。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def client():
    """测试客户端。"""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.mark.skip(reason="需要真实模型和依赖，CI 环境运行")
def test_upload_txt(client):
    """测试上传 TXT 文件。"""
    response = client.post(
        "/api/upload",
        files={"file": ("test.txt", b"Hello RAG world. This is a test document.", "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "document_id" in data["data"]
    assert data["data"]["status"] == "indexed"


@pytest.mark.skip(reason="需要真实模型和依赖")
def test_upload_unsupported_type(client):
    """测试上传不支持的文件类型。"""
    response = client.post(
        "/api/upload",
        files={"file": ("test.xlsx", b"fake content", "application/octet-stream")},
    )
    assert response.status_code == 400
