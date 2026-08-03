"""WeKnora HTTP 客户端。"""
import json as _json
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


async def get_knowledge(knowledge_id: str) -> dict[str, Any]:
    """查询单个 knowledge 的最新状态。"""
    async with _client() as c:
        resp = await c.get(f"/api/v1/knowledge/{knowledge_id}")
    if resp.status_code != 200:
        raise WeknoraError(resp.status_code, "查询文档状态失败", _safe_json(resp))
    data = resp.json()
    return data.get("data") or data


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
