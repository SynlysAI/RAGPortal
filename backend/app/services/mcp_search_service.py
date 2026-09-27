"""在 Token 授权范围内执行跨知识库检索。"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.core.weknora import WeknoraError

MAX_CONTENT_LENGTH = 600
MAX_CAPTION_LENGTH = 160


def _visible_text(value: Any, limit: int) -> str:
    """去掉上游混入的推理前缀并截取可展示文本。

    Args:
        value: WeKnora 返回的文本值。
        limit: 最大字符数。

    Returns:
        适合工具结果展示的短文本。
    """
    if not isinstance(value, str):
        return ""
    text = value.rsplit("</think>", 1)[-1].strip()
    text = re.sub(r"!\[[^\]]*\]\(\s*resource://[^)]*\)", "", text)
    text = re.sub(r"<image[^>]*resource://[^>]*>.*?</image>", "", text, flags=re.DOTALL)
    return text.strip()[:limit]


def _compact_images(raw_info: Any) -> list[dict[str, str]]:
    """只保留图片引用和短说明，不返回冗长 OCR。

    Args:
        raw_info: WeKnora image_info 字符串或列表。

    Returns:
        精简的图片引用列表。
    """
    if isinstance(raw_info, str):
        try:
            raw_info = json.loads(raw_info)
        except ValueError:
            return []
    if not isinstance(raw_info, list):
        return []
    images = []
    for entry in raw_info[:3]:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url") or entry.get("original_url")
        if not isinstance(url, str) or not url.startswith("resource://"):
            continue
        images.append({
            "_resource_path": url,
            "caption": _visible_text(entry.get("caption"), MAX_CAPTION_LENGTH),
        })
    return images


def _compact_hit(item: dict[str, Any], kb_id: str, kb_name: str) -> dict[str, Any]:
    """把上游检索命中压缩为可追溯且可阅读的字段。

    Args:
        item: WeKnora 原始检索结果。
        kb_id: 已授权知识库 ID。
        kb_name: 知识库显示名称。

    Returns:
        不含内部元数据和重复长文本的命中结果。
    """
    hit = {
        "id": item.get("id"),
        "document_id": item.get("knowledge_id"),
        "knowledge_id": item.get("knowledge_id"),
        "knowledge_title": item.get("knowledge_title"),
        "knowledge_filename": item.get("knowledge_filename"),
        "content": _visible_text(
            item.get("content") or item.get("matched_content"),
            MAX_CONTENT_LENGTH,
        ),
        "kb_id": kb_id,
        "kb_name": kb_name,
        "score": item.get("score"),
        "chunk_index": item.get("chunk_index"),
        "chunk_type": item.get("chunk_type"),
    }
    images = _compact_images(item.get("image_info"))
    if images:
        hit["image_info"] = images
    return hit


def format_search_text(result: dict[str, Any]) -> str:
    """将结构化命中呈现为短文本，避免重复打印整个 JSON。

    Args:
        result: 已精简的检索结果。

    Returns:
        带来源和文档 ID 的可读摘要。
    """
    lines = []
    for index, hit in enumerate(result.get("items", []), start=1):
        title = hit.get("knowledge_title") or hit.get("knowledge_filename") or "未命名文档"
        lines.append(
            f"{index}. {title} | 知识库：{hit.get('kb_name') or hit.get('kb_id')} "
            f"| 文档 ID：{hit.get('document_id') or '未知'}"
        )
        snippet = _visible_text(hit.get("content"), 220)
        if snippet:
            lines.append(snippet)
        if hit.get("image_info"):
            lines.append("含图片；图片链接见后续 Markdown 图片。")
    if result.get("partial"):
        lines.append("部分知识库检索失败，详情见结构化结果的 errors。")
    return "\n".join(lines) if lines else "未找到相关文档。"


def resolve_search_scope(
    arguments: dict[str, Any], allowed_ids: set[str],
) -> list[str]:
    """解析并验证检索范围，缺省时选择全部授权库。

    Args:
        arguments: MCP Tool 参数。
        allowed_ids: Token 绑定的知识库 ID 集合。

    Returns:
        去重后的知识库 ID 列表。
    """
    if "kb_id" in arguments and "kb_ids" in arguments:
        raise ValueError("kb_id 和 kb_ids 不能同时提供")
    if "kb_id" in arguments:
        selected = [arguments["kb_id"]]
    elif "kb_ids" in arguments:
        selected = arguments["kb_ids"]
    else:
        selected = sorted(allowed_ids)
    if not isinstance(selected, list) or not selected:
        raise ValueError("没有可检索的知识库，请提供非空范围或绑定知识库")
    if any(not isinstance(item, str) or not item.strip() for item in selected):
        raise ValueError("知识库 ID 必须是非空字符串")
    selected = list(dict.fromkeys(item.strip() for item in selected))
    if not set(selected) <= allowed_ids:
        raise ValueError("当前 Token 无权访问指定知识库（未绑定）")
    return selected


async def search_libraries(
    query: str,
    kb_ids: list[str],
    top_k: int,
    names: dict[str, str],
    search_one: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """限制并发检索各库，按库内排名交错合并结果。

    Args:
        query: 检索问题。
        kb_ids: 已验证的授权知识库范围。
        top_k: 最终返回结果数上限。
        names: 知识库 ID 到名称的映射。
        search_one: 项目现有的单库异步检索函数。

    Returns:
        含来源标识、检索范围和部分失败信息的检索结果。
    """
    semaphore = asyncio.Semaphore(5)

    async def retrieve(kb_id: str) -> tuple[list[dict], dict | None]:
        """检索一个知识库并规范化上游结果。

        Args:
            kb_id: 已授权知识库 ID。

        Returns:
            命中条目列表及可选的失败信息。
        """
        try:
            async with semaphore:
                payload = await search_one(kb_id=kb_id, query=query, top_k=top_k)
            if isinstance(payload, list):
                items = payload
            elif isinstance(payload, dict):
                items = payload.get(
                    "items", payload.get("results", payload.get("data")),
                )
            else:
                items = None
            if not isinstance(items, list) or any(
                not isinstance(item, dict) for item in items
            ):
                raise WeknoraError(502, "无法识别 WeKnora 检索结果格式")
            return [
                _compact_hit(item, kb_id, names.get(kb_id, kb_id))
                for item in items
            ], None
        except (WeknoraError, httpx.HTTPError) as exc:
            status = exc.status if isinstance(exc, WeknoraError) else 502
            return [], {
                "kb_id": kb_id,
                "kb_name": names.get(kb_id, kb_id),
                "status": status,
                "message": "该知识库检索失败，请重试",
            }

    results = await asyncio.gather(*(retrieve(kb_id) for kb_id in kb_ids))
    errors = [error for _, error in results if error is not None]
    if len(errors) == len(kb_ids):
        raise ValueError("所选知识库均检索失败，请检查 WeKnora 服务和接口")
    merged = []
    for rank in range(top_k):
        for items, _ in results:
            if rank < len(items):
                merged.append(items[rank])
        if len(merged) >= top_k:
            break
    return {
        "items": merged[:top_k],
        "kb_ids": kb_ids,
        "partial": bool(errors),
        "errors": errors,
        "ranking": "按各知识库内部排名交错合并",
    }
