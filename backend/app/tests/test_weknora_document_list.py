"""WeKnora 文档列表协议测试。"""

import httpx
import pytest

from app.core import weknora


@pytest.mark.asyncio
async def test_list_knowledge_page_reads_weknora_documents(monkeypatch):
    """直接从 WeKnora 的知识库文档接口读取分页结果。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    def respond(request):
        """验证文档列表请求并返回一个文档。"""
        assert request.url.path == "/api/v1/knowledge-bases/kb-a/knowledge"
        assert request.url.params["page"] == "2"
        assert request.url.params["page_size"] == "10"
        return httpx.Response(200, json={
            "success": True,
            "data": [{"id": "wk-1", "knowledge_base_id": "kb-a"}],
            "page": 2,
            "page_size": 10,
            "total": 11,
        })

    monkeypatch.setattr(weknora, "_client", lambda: httpx.AsyncClient(
        base_url="https://weknora.test", transport=httpx.MockTransport(respond),
    ))

    result = await weknora.list_knowledge_page("kb-a", page=2, page_size=10)

    assert result["items"][0]["id"] == "wk-1"
    assert result["total"] == 11
