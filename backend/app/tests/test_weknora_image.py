"""WeKnora 检索图片读取测试。"""

import httpx
import pytest

from app.core import weknora


@pytest.mark.asyncio
async def test_download_search_image_uses_kb_scoped_resource_api(monkeypatch):
    """使用知识库范围内的资源接口读取图片。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    def respond(request):
        """核对资源 URL 与查询参数。"""
        assert request.url.path == "/api/v1/knowledge-bases/kb-a/files"
        assert request.url.params["file_path"] == "resource://abc123"
        return httpx.Response(200, content=b"jpeg", headers={
            "Content-Type": "image/jpeg",
        })

    monkeypatch.setattr(weknora, "_client", lambda: httpx.AsyncClient(
        base_url="https://weknora.test", transport=httpx.MockTransport(respond),
    ))
    content, mime_type = await weknora.download_search_image(
        "kb-a", "resource://abc123",
    )
    assert content == b"jpeg"
    assert mime_type == "image/jpeg"


@pytest.mark.asyncio
async def test_download_search_image_rejects_external_url():
    """检索结果不能驱使后端抓取任意外部地址。"""
    with pytest.raises(ValueError):
        await weknora.download_search_image(
            "kb-a", "https://untrusted.example/image.png",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mime_type", ["text/html", "image/svg+xml"])
async def test_download_search_image_rejects_unsupported_content(monkeypatch, mime_type):
    """拒绝非位图与可能包含脚本的 SVG 图片。

    Args:
        monkeypatch: pytest 注入替换工具。
        mime_type: 模拟的资源 MIME 类型。
    """
    monkeypatch.setattr(weknora, "_client", lambda: httpx.AsyncClient(
        base_url="https://weknora.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(
            200, content=b"unsafe", headers={"Content-Type": mime_type},
        )),
    ))
    with pytest.raises(ValueError):
        await weknora.download_search_image("kb-a", "resource://abc123")


@pytest.mark.asyncio
async def test_download_search_image_rejects_oversized_bitmap(monkeypatch):
    """超过单图上限的图片不进入 MCP 返回值。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    monkeypatch.setattr(weknora, "_client", lambda: httpx.AsyncClient(
        base_url="https://weknora.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(
            200, content=b"oversized", headers={"Content-Type": "image/jpeg"},
        )),
    ))
    with pytest.raises(ValueError):
        await weknora.download_search_image(
            "kb-a", "resource://abc123", max_size_bytes=4,
        )
