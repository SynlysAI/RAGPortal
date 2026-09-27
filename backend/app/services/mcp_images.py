"""将 WeKnora 检索图片转换为 MCP 图片内容块。"""

import base64
import json
from typing import Any

import httpx

from app.core.weknora import WeknoraError, download_search_image

MAX_SEARCH_IMAGES = 3


def _image_entries(raw_info: Any) -> list[dict]:
    """解析 WeKnora image_info 的结构化图片列表。

    Args:
        raw_info: 检索结果中的 image_info 字段。

    Returns:
        可供进一步验证的图片字典列表。
    """
    if isinstance(raw_info, str):
        try:
            raw_info = json.loads(raw_info)
        except ValueError:
            return []
    if not isinstance(raw_info, list):
        return []
    return [entry for entry in raw_info if isinstance(entry, dict)]


async def search_image_blocks(result: dict[str, Any]) -> list[dict[str, str]]:
    """为检索结果附加最多三张已授权知识库的图片。

    Args:
        result: rag_search 已完成知识库授权校验的结构化结果。

    Returns:
        交替排列的来源文字与 MCP 图片内容块。
    """
    blocks = []
    for index, hit in enumerate(result.get("items", []), start=1):
        kb_id = hit.get("kb_id")
        if not isinstance(kb_id, str) or not kb_id:
            continue
        for entry in _image_entries(hit.get("image_info")):
            resource_path = entry.get("url") or entry.get("original_url")
            if not isinstance(resource_path, str) or not resource_path.startswith("resource://"):
                continue
            try:
                data, mime_type = await download_search_image(kb_id, resource_path)
            except (ValueError, WeknoraError, httpx.HTTPError):
                continue
            caption = str(entry.get("caption") or "").strip()[:300]
            knowledge_id = str(hit.get("document_id") or hit.get("knowledge_id") or "")
            label = f"检索结果第 {index} 条的图片，文档 ID：{knowledge_id}"
            if caption:
                label += f"。图片说明：{caption}"
            blocks.extend([
                {"type": "text", "text": label},
                {
                    "type": "image",
                    "data": base64.b64encode(data).decode("ascii"),
                    "mimeType": mime_type,
                },
            ])
            if len(blocks) // 2 >= MAX_SEARCH_IMAGES:
                return blocks
    return blocks
