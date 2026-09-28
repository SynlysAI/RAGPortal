"""检索命中图片 Markdown 链接测试。"""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from app.api import mcp
from app.services import mcp_images


@pytest.mark.asyncio
async def test_search_image_blocks_create_markdown_links(monkeypatch):
    """结构化 image_info 转换为短期 Markdown 图片链接。"""
    ticket_mock = AsyncMock(return_value=SimpleNamespace(
        secret="rim_temporary",
        expires_at=datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc),
    ))
    monkeypatch.setattr(mcp_images, "create_image_ticket", ticket_mock)
    monkeypatch.setattr(mcp_images, "get_settings", lambda: SimpleNamespace(
        mcp_public_base_url="https://rag.example.com",
        frontend_origin="http://localhost:3002",
        mcp_image_url_ttl_seconds=2_592_000,
        app_env="production",
    ))
    result = {"items": [{
        "kb_id": "kb-a",
        "document_id": "wk-1",
        "image_info": json.dumps([{
            "url": "resource://abc123",
            "caption": "实验布局图",
        }]),
    }]}

    blocks = await mcp_images.search_image_markdown_blocks(result, None, 7)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert "![实验布局图]" in blocks[0]["text"]
    assert "https://rag.example.com/api/mcp/images/rim_temporary" in blocks[0]["text"]
    ticket_mock.assert_awaited_once_with(
        session=None,
        api_token_id=7,
        knowledge_id="wk-1",
        kb_id="kb-a",
        resource_path="resource://abc123",
        ttl_seconds=2_592_000,
    )


@pytest.mark.asyncio
async def test_mcp_search_response_only_contains_json_text(monkeypatch):
    """检索响应仅返回 JSON 文本，图片链接保留在 image_info 中。

    Args:
        monkeypatch: 用于替换 Token 校验、检索数据和图片凭证依赖。
    """
    result = {"items": [{
        "kb_id": "kb-a", "document_id": "wk-1",
        "knowledge_title": "实验论文",
        "image_info": [{
            "_resource_path": "resource://abc123", "caption": "凝胶电泳结果图",
        }],
    }]}
    monkeypatch.setattr(mcp, "_get_token", AsyncMock(return_value=SimpleNamespace(
        id=1, user_id="u1", permissions_json='["documents:search"]',
        knowledge_base_ids_json='["kb-a"]',
    )))
    monkeypatch.setattr(mcp, "call_tool", AsyncMock(return_value=result))
    monkeypatch.setattr(mcp_images, "create_image_ticket", AsyncMock(
        return_value=SimpleNamespace(
            secret="rim_x",
            expires_at=datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc),
        ),
    ))
    monkeypatch.setattr(mcp_images, "get_settings", lambda: SimpleNamespace(
        mcp_public_base_url="https://rag.example.com",
        frontend_origin="http://localhost:3002",
        mcp_image_url_ttl_seconds=2_592_000,
        app_env="production",
    ))
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "rag_search", "arguments": {"query": "图"}},
    }).encode("utf-8")

    async def receive():
        """向测试请求提供 JSON-RPC 请求体。"""
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request({
        "type": "http", "method": "POST", "path": "/api/mcp",
        "headers": [(b"content-type", b"application/json")],
    }, receive)
    response = await mcp.mcp_endpoint(request, None)

    content = response["result"]["content"]
    assert len(content) == 1
    assert content[0]["type"] == "text"
    serialized = json.loads(content[0]["text"])
    assert serialized == response["result"]["structuredContent"]
    assert serialized["items"][0]["image_info"] == [{
        "caption": "凝胶电泳结果图",
        "markdown_url": "https://rag.example.com/api/mcp/images/rim_x",
    }]
    assert "resource://" not in content[0]["text"]


@pytest.mark.asyncio
async def test_search_image_links_reject_invalid_public_url(monkeypatch):
    """生产环境拒绝 HTTP 图片链接。"""
    monkeypatch.setattr(mcp_images, "get_settings", lambda: SimpleNamespace(
        mcp_public_base_url="http://rag.example.com",
        frontend_origin="http://localhost:3002",
        mcp_image_url_ttl_seconds=2_592_000,
        app_env="production",
    ))
    with pytest.raises(ValueError):
        await mcp_images.search_image_markdown_blocks({"items": []}, None, 7)
