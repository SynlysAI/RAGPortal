"""WeKnora 混合检索协议验证。"""

import json

import httpx
import pytest

from app.core import weknora


@pytest.mark.parametrize("items", [[], None, [{"id": "chunk", "content": "实验"}]])
async def test_search_uses_hybrid_search_contract(monkeypatch, items):
    """检索采用 WeKnora 真实路由和参数，空结果仍返回列表。

    Args:
        monkeypatch: pytest 注入替换工具。
        items: 上游返回的命中列表或 null。
    """
    def respond(request):
        """验证请求协议并模拟服务端响应。"""
        assert request.url.path == "/api/v1/knowledge-bases/kb-a/hybrid-search"
        assert request.url.params.get("resource_urls") == "public"
        assert json.loads(request.content) == {"query_text": "实验", "match_count": 10}
        return httpx.Response(200, json={"success": True, "data": items})

    monkeypatch.setattr(weknora, "_client", lambda: httpx.AsyncClient(
        base_url="https://weknora.test", transport=httpx.MockTransport(respond),
    ))
    result = await weknora.search_knowledge(kb_id="kb-a", query="实验", top_k=10)
    assert result == {"items": items or []}


async def test_search_falls_back_without_public_mode_on_restricted_key(monkeypatch):
    """受限 API Key 被直链模式拒绝时退回默认模式重试。"""
    calls = []

    def respond(request):
        """记录每次请求的 resource_urls 参数并按需返回 403。"""
        calls.append(request.url.params.get("resource_urls"))
        if request.url.params.get("resource_urls") == "public":
            return httpx.Response(403, json={
                "error": {"message": "resource_urls=public is not available"},
            })
        return httpx.Response(200, json={"success": True, "data": [{"id": "chunk"}]})

    monkeypatch.setattr(weknora, "_client", lambda: httpx.AsyncClient(
        base_url="https://weknora.test", transport=httpx.MockTransport(respond),
    ))
    result = await weknora.search_knowledge(kb_id="kb-a", query="实验", top_k=5)
    assert calls == ["public", None]
    assert result == {"items": [{"id": "chunk"}]}
