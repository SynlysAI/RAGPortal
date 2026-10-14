"""将 WeKnora 检索图片转换为 Markdown 短期链接。"""

from typing import Any
from urllib.parse import quote, urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.download_ticket_service import create_image_ticket

MAX_SEARCH_IMAGES = 3
MAX_CAPTION_LENGTH = 300


def _resource_image_entries(raw_info: Any) -> list[tuple[int, dict]]:
    """挑出需要门户代取的 resource:// 图片条目。

    Args:
        raw_info: 精简后的 image_info 列表。

    Returns:
        (原始下标, 条目) 列表；http(s) 直链条目不需要签发凭证，不返回。
    """
    if not isinstance(raw_info, list):
        return []
    entries = []
    for index, entry in enumerate(raw_info):
        if not isinstance(entry, dict):
            continue
        resource_path = entry.get("_resource_path")
        if isinstance(resource_path, str) and resource_path.startswith("resource://"):
            entries.append((index, {
                "_resource_path": resource_path,
                "caption": entry.get("caption", ""),
            }))
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
    """把命中的 resource:// 图片改写为门户短期链接并生成 Markdown 文本。

    http(s) 直链图片（WeKnora resource_urls=public 的返回）本身可加载，
    原样保留在 image_info 中，不经过本函数签发。

    Args:
        result: 已完成知识库授权校验的检索结果。
        session: 数据库会话。
        api_token_id: 当前 MCP API Token ID。

    Returns:
        MCP text 内容块；不返回 Base64 图片，便于非多模态模型处理。
    """
    ttl_seconds = get_settings().mcp_image_url_ttl_seconds
    base_url: str | None = None
    blocks: list[dict[str, str]] = []
    for index, hit in enumerate(result.get("items", []), start=1):
        kb_id = hit.get("kb_id")
        knowledge_id = str(hit.get("document_id") or hit.get("knowledge_id") or "")
        if not isinstance(kb_id, str) or not kb_id or not knowledge_id:
            continue
        image_entries = hit.get("image_info")
        for entry_index, entry in _resource_image_entries(image_entries):
            resource_path = entry.get("_resource_path")
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
            if base_url is None:
                # 延迟到确有图片需要签发时才校验，直链结果不受本部署配置影响。
                base_url = _public_base_url()
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
