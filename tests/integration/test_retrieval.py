"""检索流程集成测试。"""
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
def test_retrieval_flow(client):
    """测试完整检索流程：上传 -> 问答 -> 验证 sources。"""
    # 1. 上传文档
    upload_resp = client.post(
        "/api/upload",
        files={"file": ("test.txt", b"RAG is retrieval augmented generation. It combines search and LLM.", "text/plain")},
    )
    doc_id = upload_resp.json()["data"]["document_id"]

    # 2. 问答
    chat_resp = client.post(
        "/api/chat",
        json={"question": "What is RAG?", "document_ids": [doc_id]},
    )
    data = chat_resp.json()["data"]
    assert "answer" in data
    assert len(data["sources"]) > 0
    assert data["sources"][0]["document_id"] == doc_id
