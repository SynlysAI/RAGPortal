"""从 WeKnora 回写历史知识到本地上传记录。"""
import json
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.weknora import list_knowledge_page
from app.models.upload import Upload
from app.services.kb_service import get_kb_list
from app.services.sync_service import _map_status

SYSTEM_USER_ID = "system"
SYSTEM_USERNAME = "系统上传"
UNKNOWN_SOURCE = "来源未知"


def _parse_metadata(raw: Any) -> dict[str, Any]:
    """解析 WeKnora knowledge metadata。

    Args:
        raw: WeKnora 返回的 metadata，可能是 dict、JSON 字符串或空值。

    Returns:
        解析后的 metadata 字典。
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(data, dict):
            return data
    return {}


def _extract_uploader(metadata: dict[str, Any]) -> dict[str, str]:
    """从 metadata 中提取上传者信息。

    Args:
        metadata: 已解析的 metadata 字典。

    Returns:
        包含 uploader_user_id、uploader_username、uploader_organization 的字典。
    """
    user_id = str(metadata.get("uploader_id") or metadata.get("uploader_user_id") or "").strip()
    username = str(metadata.get("uploader_name") or metadata.get("uploader_username") or "").strip()
    organization = str(metadata.get("uploader_org") or metadata.get("uploader_organization") or "").strip()
    if not user_id and not username:
        return {
            "uploader_user_id": SYSTEM_USER_ID,
            "uploader_username": SYSTEM_USERNAME,
            "uploader_organization": UNKNOWN_SOURCE,
        }
    return {
        "uploader_user_id": user_id or username,
        "uploader_username": username or user_id,
        "uploader_organization": organization or "",
    }


def _knowledge_file_name(knowledge: dict[str, Any]) -> str:
    """从 knowledge 对象中推断文件名。

    Args:
        knowledge: WeKnora knowledge 对象。

    Returns:
        文件名或标题兜底。
    """
    return str(
        knowledge.get("file_name")
        or knowledge.get("title")
        or knowledge.get("source")
        or knowledge.get("id")
        or "untitled"
    )


def _knowledge_file_type(knowledge: dict[str, Any], file_name: str) -> str:
    """从 knowledge 对象中推断文件类型。

    Args:
        knowledge: WeKnora knowledge 对象。
        file_name: 已推断的文件名。

    Returns:
        文件扩展名或 knowledge 类型。
    """
    file_type = str(knowledge.get("file_type") or "").strip().lower().lstrip(".")
    if file_type:
        return file_type[:16]
    suffix = PurePath(file_name).suffix.lower().lstrip(".")
    if suffix:
        return suffix[:16]
    return str(knowledge.get("type") or "unknown")[:16]


def _knowledge_uploaded_at(knowledge: dict[str, Any]) -> str:
    """从 knowledge 对象中推断上传时间。

    Args:
        knowledge: WeKnora knowledge 对象。

    Returns:
        上传时间 ISO 字符串。
    """
    value = knowledge.get("created_at") or knowledge.get("updated_at")
    if value:
        return str(value)
    return datetime.now(timezone.utc).isoformat()


def _status_and_error(knowledge: dict[str, Any]) -> tuple[str, str]:
    """从 knowledge 对象中提取 RAGPortal 状态和错误信息。

    Args:
        knowledge: WeKnora knowledge 对象。

    Returns:
        (parse_status, parse_error)。
    """
    status, _ = _map_status(str(knowledge.get("parse_status") or ""))
    if status != "failed":
        return status, ""
    return status, str(knowledge.get("error_message") or knowledge.get("error") or "")


async def _upsert_knowledge(
    session: AsyncSession,
    kb: dict[str, Any],
    knowledge: dict[str, Any],
) -> str:
    """将单条 WeKnora knowledge 写入或更新到本地库。

    Args:
        session: 异步数据库会话。
        kb: 当前知识库信息。
        knowledge: WeKnora knowledge 对象。

    Returns:
        `created`、`updated` 或 `skipped`。
    """
    knowledge_id = str(knowledge.get("id") or "").strip()
    if not knowledge_id:
        return "skipped"

    file_name = _knowledge_file_name(knowledge)
    file_type = _knowledge_file_type(knowledge, file_name)
    parse_status, parse_error = _status_and_error(knowledge)
    metadata = _parse_metadata(knowledge.get("metadata"))
    uploader = _extract_uploader(metadata)
    now = datetime.now(timezone.utc).isoformat()

    result = await session.execute(
        select(Upload).where(Upload.knowledge_id == knowledge_id)
    )
    record = result.scalars().first()
    if record:
        record.kb_id = str(kb.get("id") or knowledge.get("knowledge_base_id") or "")
        record.kb_name = str(kb.get("name") or record.kb_name or "")
        record.file_name = file_name
        record.file_type = file_type
        record.file_size = int(knowledge.get("file_size") or record.file_size or 0)
        record.parse_status = parse_status
        record.parse_error = parse_error
        record.last_synced_at = now
        if record.uploader_user_id == SYSTEM_USER_ID and uploader["uploader_user_id"] != SYSTEM_USER_ID:
            record.uploader_user_id = uploader["uploader_user_id"]
            record.uploader_username = uploader["uploader_username"]
            record.uploader_organization = uploader["uploader_organization"]
        return "updated"

    session.add(
        Upload(
            knowledge_id=knowledge_id,
            kb_id=str(kb.get("id") or knowledge.get("knowledge_base_id") or ""),
            kb_name=str(kb.get("name") or ""),
            uploader_user_id=uploader["uploader_user_id"],
            uploader_username=uploader["uploader_username"],
            uploader_organization=uploader["uploader_organization"],
            file_name=file_name,
            file_type=file_type,
            file_size=int(knowledge.get("file_size") or 0),
            parse_status=parse_status,
            parse_error=parse_error,
            weknora_task_id=str(knowledge.get("task_id") or ""),
            uploaded_at=_knowledge_uploaded_at(knowledge),
            last_synced_at=now,
        )
    )
    return "created"


async def backfill_uploads_from_weknora(
    session: AsyncSession,
    page_size: int = 100,
    max_pages_per_kb: int = 100,
) -> dict[str, int]:
    """从 WeKnora 扫描历史知识并回写本地上传记录。

    Args:
        session: 异步数据库会话。
        page_size: 每页拉取数量。
        max_pages_per_kb: 每个知识库最多扫描页数，避免异常分页无限循环。

    Returns:
        回写统计信息。
    """
    stats = {"scanned": 0, "created": 0, "updated": 0, "skipped": 0}
    kbs = await get_kb_list(refresh=True)
    for kb in kbs:
        kb_id = str(kb.get("id") or "").strip()
        if not kb_id:
            continue
        for page in range(1, max_pages_per_kb + 1):
            data = await list_knowledge_page(kb_id, page=page, page_size=page_size)
            items = data["items"]
            if not items:
                break
            for knowledge in items:
                stats["scanned"] += 1
                action = await _upsert_knowledge(session, kb, knowledge)
                stats[action] += 1
            await session.commit()
            total = int(data.get("total") or 0)
            if total and page * page_size >= total:
                break
            if len(items) < page_size:
                break
    return stats
