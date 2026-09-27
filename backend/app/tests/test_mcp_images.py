"""检索命中图片的 MCP 返回测试。"""

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from app.api import mcp
from app.services import mcp_images


@pytest.mark.asyncio
async def test_search_image_blocks_include_actual_image_data(monkeypatch):
    """结构化 image_info 转换为 MCP 图片内容块。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    image_mock = AsyncMock(return_value=(b"jpeg", "image/jpeg"))
    monkeypatch.setattr(mcp_images, "download_search_image", image_mock)
    result = {"items": [{
        "kb_id": "kb-a",
        "knowledge_id": "wk-1",
        "knowledge_title": "实验论文",
        "image_info": json.dumps([{
            "url": "resource://abc123",
            "caption": "实验布局图",
        }]),
    }]}

    blocks = await mcp_images.search_image_blocks(result)

    assert blocks[0]["type"] == "text"
    assert "实验布局图" in blocks[0]["text"]
    assert blocks[1] == {
        "type": "image",
        "data": base64.b64encode(b"jpeg").decode("ascii"),
        "mimeType": "image/jpeg",
    }
    image_mock.assert_awaited_once_with("kb-a", "resource://abc123")


@pytest.mark.asyncio
async def test_mcp_search_response_contains_image_block(monkeypatch):
    """tools/call 的检索响应实际包含图片内容块。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    result = {"items": [{
        "kb_id": "kb-a", "knowledge_id": "wk-1",
        "image_info": '[{"url":"resource://abc123"}]',
    }]}
    monkeypatch.setattr(mcp, "_get_token", AsyncMock(return_value=SimpleNamespace(
        id=1,
        user_id="u1",
        permissions_json='["documents:search"]',
        knowledge_base_ids_json='["kb-a"]',
    )))
    monkeypatch.setattr(mcp, "call_tool", AsyncMock(return_value=result))
    monkeypatch.setattr(
        mcp_images, "download_search_image",
        AsyncMock(return_value=(b"jpeg", "image/jpeg")),
    )
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

    assert response["result"]["content"][1]["type"] == "text"
    assert response["result"]["content"][2]["type"] == "image"
    assert response["result"]["structuredContent"] == result
