"""WeKnora HTTP 客户端。"""
import json as _json
import re
from typing import Any, Optional

import httpx

from app.core.config import get_settings


class WeknoraError(Exception):
    """WeKnora API 错误。"""

    def __init__(self, status: int, message: str, payload: Optional[dict] = None):
        super().__init__(f"[{status}] {message}")
        self.status = status
        self.message = message
        self.payload = payload or {}


def _client() -> httpx.AsyncClient:
    """构造带 API Key 的 client。"""
    s = get_settings()
    return httpx.AsyncClient(
        base_url=s.weknora_base_url,
        headers={"X-API-Key": s.weknora_api_key},
        timeout=30,
    )


def _safe_json(resp: httpx.Response) -> dict:
    """安全解析响应 JSON,失败时回退到 {"raw": text}。"""
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _extract_response_data(payload: dict) -> dict[str, Any]:
    """从 WeKnora 标准响应中提取 data 对象。

    Args:
        payload: WeKnora API 返回的完整 JSON 字典。

    Returns:
        响应中的 data 字典；旧格式或非字典 data 时回退为原始响应。
    """
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload


async def list_knowledge_bases() -> list[dict[str, Any]]:
    """获取当前 API Key 能访问的所有知识库。

    Returns:
        KB 字典列表,每个含 id/name/type。
    """
    async with _client() as c:
        resp = await c.get("/api/v1/knowledge-bases")
    if resp.status_code != 200:
        raise WeknoraError(resp.status_code, "拉取知识库列表失败", _safe_json(resp))
    data = resp.json()
    items = data.get("data") or data.get("items") or data
    if not isinstance(items, list):
        return []
    return [
        {"id": kb.get("id"), "name": kb.get("name"), "type": kb.get("type", "document")}
        for kb in items
    ]


async def create_knowledge_base(payload: dict[str, Any]) -> dict[str, Any]:
    """创建知识库。"""
    async with _client() as c:
        resp = await c.post("/api/v1/knowledge-bases", json=payload)
    if resp.status_code not in (200, 201):
        raise WeknoraError(
            resp.status_code,
            _safe_json(resp).get("detail", "创建知识库失败"),
            _safe_json(resp),
        )
    return _extract_response_data(_safe_json(resp))


async def get_knowledge(knowledge_id: str) -> dict[str, Any]:
    """查询单个 knowledge 的最新状态。"""
    async with _client() as c:
        resp = await c.get(f"/api/v1/knowledge/{knowledge_id}")
    if resp.status_code != 200:
        raise WeknoraError(resp.status_code, "查询文档状态失败", _safe_json(resp))
    data = resp.json()
    return data.get("data") or data


async def search_knowledge(*, kb_id: str, query: str, top_k: int = 5) -> dict[str, Any]:
    """代理 WeKnora 单库混合检索并规范化命中列表。

    Args:
        kb_id: 已授权知识库 ID。
        query: 检索问题。
        top_k: 单库召回条数上限。

    Returns:
        包含 items 命中列表的字典。
    """
    async with _client() as c:
        resp = await c.post(
            f"/api/v1/knowledge-bases/{kb_id}/hybrid-search",
            json={"query_text": query, "match_count": max(1, min(top_k, 20))},
        )
    if resp.status_code != 200:
        raise WeknoraError(resp.status_code, "WeKnora 检索失败", _safe_json(resp))
    payload = _safe_json(resp)
    if "data" not in payload:
        raise WeknoraError(502, "WeKnora 检索响应缺少 data")
    items = payload["data"]
    if items is None:
        items = []
    if not isinstance(items, list):
        raise WeknoraError(502, "WeKnora 检索响应 data 必须是列表")
    return {"items": items}


async def download_knowledge_file(knowledge_id: str) -> tuple[bytes, str]:
    """下载 WeKnora 中 knowledge 对应的原始文件。"""
    async with _client() as c:
        resp = await c.get(f"/api/v1/knowledge/{knowledge_id}/download")
    if resp.status_code != 200:
        raise WeknoraError(resp.status_code, "下载文档失败", _safe_json(resp))
    return resp.content, resp.headers.get("content-type", "application/octet-stream")


async def download_search_image(
    kb_id: str,
    resource_path: str,
    max_size_bytes: int = 2 * 1024 * 1024,
) -> tuple[bytes, str]:
    """从 WeKnora 已授权知识库读取检索命中的位图图片。

    Args:
        kb_id: 命中所属知识库 ID。
        resource_path: image_info 中的 resource:// 资源引用。
        max_size_bytes: 单张图片允许返回的最大字节数。

    Returns:
        图片内容和 MCP 可识别的 MIME 类型。

    Raises:
        ValueError: 引用格式不合法或资源内容不符合位图要求。
        WeknoraError: WeKnora 资源接口返回失败。
    """
    if not re.fullmatch(r"resource://[A-Za-z0-9_-]+", resource_path):
        raise ValueError("仅支持 WeKnora resource:// 图片引用")
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    chunks = []
    size = 0
    async with _client() as client:
        async with client.stream(
            "GET",
            f"/api/v1/knowledge-bases/{kb_id}/files",
            params={"file_path": resource_path},
        ) as response:
            if response.status_code != 200:
                raise WeknoraError(response.status_code, "读取检索图片失败")
            mime_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if mime_type not in allowed_types:
                raise ValueError("检索资源不是受支持的位图格式")
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > max_size_bytes:
                    raise ValueError("检索图片超过大小限制")
                chunks.append(chunk)
    if size == 0:
        raise ValueError("检索图片内容为空")
    return b"".join(chunks), mime_type


async def list_knowledge_page(
    kb_id: str,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """分页获取指定知识库下的 knowledge 列表。

    Args:
        kb_id: 知识库 ID。
        page: 页码，从 1 开始。
        page_size: 每页条数。

    Returns:
        包含 items/page/page_size/total 的分页结果。

    Raises:
        WeknoraError: WeKnora 返回非 2xx。
    """
    async with _client() as c:
        resp = await c.get(
            f"/api/v1/knowledge-bases/{kb_id}/knowledge",
            params={"page": page, "page_size": page_size},
        )
    payload = _safe_json(resp)
    if resp.status_code != 200:
        raise WeknoraError(
            resp.status_code,
            payload.get("detail") or payload.get("message") or "拉取知识列表失败",
            payload,
        )
    items = payload.get("data") or payload.get("items") or []
    if not isinstance(items, list):
        items = []
    return {
        "items": items,
        "page": payload.get("page", page),
        "page_size": payload.get("page_size", page_size),
        "total": payload.get("total", len(items)),
    }


async def upload_file(
    *,
    kb_id: str,
    file_bytes: bytes,
    file_name: str,
    file_size: int,
    uploader_user_id: str,
    uploader_username: str,
    uploader_organization: str = "",
    custom_filename: str = "",
) -> dict[str, Any]:
    """代理 WeKnora 单文件上传。

    Args:
        kb_id: 目标知识库 ID。
        file_bytes: 文件二进制内容。
        file_name: 原始文件名(用于扩展名校验)。
        file_size: 文件大小(字节)。
        uploader_user_id: 上传者 AI4MS user_id。
        uploader_username: 上传者用户名(冗余快照)。
        uploader_organization: 上传者组织(冗余快照)。
        custom_filename: 自定义文件名(文件夹场景含相对路径)。

    Returns:
        WeKnora 返回的 knowledge 对象。

    Raises:
        WeknoraError: WeKnora 返回非 2xx。
    """
    metadata = {
        "uploader_id": uploader_user_id,
        "uploader_name": uploader_username,
        "uploader_org": uploader_organization,
    }
    data: dict[str, Any] = {"metadata": _json.dumps(metadata)}
    if custom_filename:
        data["fileName"] = custom_filename
    files = {"file": (file_name, file_bytes)}

    async with _client() as c:
        resp = await c.post(
            f"/api/v1/knowledge-bases/{kb_id}/knowledge/file",
            data=data,
            files=files,
        )
    if resp.status_code not in (200, 201):
        raise WeknoraError(
            resp.status_code,
            _safe_json(resp).get("detail", "上传失败"),
            _safe_json(resp),
        )
    return _extract_response_data(_safe_json(resp))
