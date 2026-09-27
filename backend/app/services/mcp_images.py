"""将 WeKnora 检索图片转换为 Markdown 短期链接。"""

import json
from typing import Any
from urllib.parse import quote, urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.download_ticket_service import create_image_ticket

MAX_SEARCH_IMAGES = 3
MAX_CAPTION_LENGTH = 300


def _image_entries(raw_info: Any) -> list[dict]:
    """解析 WeKnora image_info 的结构化图片列表。"""
    if isinstance(raw_info, str):
        try:
            raw_info = json.loads(raw_info)
        except ValueError:
            return []
    if not isinstance(raw_info, list):
        return []
    entries = []
    for entry in raw_info:
        if not isinstance(entry, dict):
            continue
        resource_path = entry.get("_resource_path") or entry.get("url") or entry.get("original_url")
        if isinstance(resource_path, str) and resource_path.startswith("resource://"):
            entries.append({
                "_resource_path": resource_path,
                "caption": entry.get("caption", ""),
            })
    return entries


def _public_base_url() -> str:
    """读取并验证图片 Markdown 链接的公网根地址。"""
    settings = get_settings()
    base_url = (settings.mcp_public_base_url or settings.frontend_origin).rstrip("/")
    parsed = urlsplit(base_url)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("MCP_PUBLIC_BASE_URL 配置无效")
    if parsed.scheme != "https" and (not local or settings.app_env == "production"):
        raise ValueError("外部图片链接必须使用 HTTPS")
    return base_url


async def search_image_markdown_blocks(
    result: dict[str, Any],
    session: AsyncSession,
    api_token_id: int,
) -> list[dict[str, str]]:
    """为检索命中生成最多三条 Markdown 图片文本。

    Args:
        result: 已完成知识库授权校验的检索结果。
        session: 数据库会话。
        api_token_id: 当前 MCP API Token ID。

    Returns:
        MCP text 内容块；不返回 Base64 图片，便于非多模态模型处理。
    """
    base_url = _public_base_url()
    ttl_seconds = get_settings().mcp_image_url_ttl_seconds
    blocks: list[dict[str, str]] = []
    for index, hit in enumerate(result.get("items", []), start=1):
        kb_id = hit.get("kb_id")
        knowledge_id = str(hit.get("document_id") or hit.get("knowledge_id") or "")
        if not isinstance(kb_id, str) or not kb_id or not knowledge_id:
            continue
        image_entries = hit.get("image_info")
        for entry_index, entry in enumerate(_image_entries(image_entries)):
            resource_path = entry.get("_resource_path")
            if not isinstance(resource_path, str) or not resource_path.startswith("resource://"):
                continue
            caption = str(entry.get("caption") or "SEM 显微图").strip()
            caption = caption.replace("]", "\\]").replace("\n", " ")[:MAX_CAPTION_LENGTH]
            public_image = {"caption": caption}
            try:
                ticket = await create_image_ticket(
                    session=session,
                    api_token_id=api_token_id,
                    knowledge_id=knowledge_id,
                    kb_id=kb_id,
                    resource_path=resource_path,
                    ttl_seconds=ttl_seconds,
                )
            except ValueError:
                if isinstance(image_entries, list) and entry_index < len(image_entries):
                    image_entries[entry_index] = public_image
                continue
            image_url = f"{base_url}/api/mcp/images/{quote(ticket.secret, safe='')}"
            public_image["markdown_url"] = image_url
            if isinstance(image_entries, list):
                image_entries[entry_index] = public_image
            blocks.append({
                "type": "text",
                "text": (
                    f"图片（检索结果第 {index} 条，文档 ID：{knowledge_id}，"
                    f"有效期至 {ticket.expires_at.isoformat()}）：\n"
                    f"![{caption}]({image_url})"
                ),
            })
            if len(blocks) >= MAX_SEARCH_IMAGES:
                return blocks
    return blocks
