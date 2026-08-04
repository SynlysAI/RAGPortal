"""解析状态懒同步服务。"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.weknora import WeknoraError, get_knowledge
from app.models.upload import Upload

DELETED_STATUS = "deleted"
DELETED_ERROR = "上游文档已删除"


def _map_status(weknora_status: str) -> tuple[str, str]:
    """WeKnora parse_status 映射到 RAGPortal 状态。

    Args:
        weknora_status: WeKnora 返回的 parse_status 原值。

    Returns:
        (ragportal_status, parse_error_placeholder)。
        failed 时 error_message 由调用方注入。
    """
    s = (weknora_status or "").lower()
    if s in ("success", "completed", "enabled"):
        return "success", ""
    if s in ("processing", "finalizing", "reprocessing"):
        return "processing", ""
    if s in ("failed", "error"):
        return "failed", ""
    return "pending", ""


async def sync_one(session: AsyncSession, upload: Upload) -> Upload:
    """拉取 WeKnora 单条最新状态并更新到 DB。

    终态(success/failed)记录不再同步。

    Args:
        session: 异步 DB 会话。
        upload: Upload 记录(已绑定到会话)。

    Returns:
        更新后的 Upload 对象。
    """
    if upload.parse_status in ("success", "failed", DELETED_STATUS):
        return upload
    try:
        data = await get_knowledge(upload.knowledge_id)
    except WeknoraError as exc:
        if exc.status != 404:
            raise
        upload.parse_status = DELETED_STATUS
        upload.parse_error = DELETED_ERROR
        upload.last_synced_at = datetime.now(timezone.utc).isoformat()
        await session.commit()
        return upload
    weknora_status = data.get("parse_status", "")
    new_status, _ = _map_status(weknora_status)
    error_msg = ""
    if new_status == "failed":
        error_msg = data.get("error_message", "") or data.get("error", "")
    file_hash = str(data.get("file_hash") or "").strip()
    upload.parse_status = new_status
    upload.parse_error = error_msg
    if file_hash:
        upload.file_hash = file_hash
    upload.last_synced_at = datetime.now(timezone.utc).isoformat()
    await session.commit()
    return upload


async def sync_pending(session: AsyncSession, limit: int = 50) -> int:
    """批量懒同步:对最近 N 条非终态记录拉取最新状态。

    单条失败不影响其他。

    Returns:
        实际同步成功的记录数。
    """
    stmt = (
        select(Upload)
        .where(Upload.parse_status.in_(("pending", "processing")))
        .order_by(Upload.uploaded_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    uploads = result.scalars().all()
    count = 0
    for upload in uploads:
        try:
            await sync_one(session, upload)
            count += 1
        except Exception:
            continue
    return count
