"""上传业务逻辑:WeKnora 调用 + SQLite 双写。"""
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.weknora import WeknoraError, upload_file as weknora_upload_file
from app.models.upload import Upload
from app.services.kb_service import find_kb, is_kb_allowed


class UploadError(Exception):
    """上传业务错误,带 status_code。"""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _file_extension(filename: str) -> str:
    """提取扩展名(小写无点)。"""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def handle_upload(
    *,
    session: AsyncSession,
    kb_id: str,
    file: UploadFile,
    uploader_user_id: str,
    uploader_username: str,
    uploader_organization: str,
    max_size_bytes: int,
    allowed_types: set[str],
) -> Upload:
    """处理一次上传:校验 → 调 WeKnora → 写 SQLite。

    Raises:
        UploadError: 业务校验失败(权限/大小/类型/重复/上游错误)。
    """
    if not await is_kb_allowed(kb_id):
        raise UploadError(403, "无权上传到此知识库")
    kb = await find_kb(kb_id)

    file_bytes = await file.read()
    if len(file_bytes) > max_size_bytes:
        raise UploadError(413, f"文件超出大小限制({max_size_bytes // (1024 * 1024)}MB)")

    ext = _file_extension(file.filename or "")
    if ext not in allowed_types:
        raise UploadError(400, f"不支持的文件类型:{ext}")

    try:
        weknora_resp = await weknora_upload_file(
            kb_id=kb_id,
            file_bytes=file_bytes,
            file_name=file.filename or "untitled",
            file_size=len(file_bytes),
            uploader_user_id=uploader_user_id,
            uploader_username=uploader_username,
            uploader_organization=uploader_organization,
            custom_filename=file.filename or "",
        )
    except WeknoraError as e:
        if e.status == 409:
            raise UploadError(409, "文件已存在") from e
        raise UploadError(e.status, e.message) from e

    knowledge_id = weknora_resp.get("id")
    if not knowledge_id:
        raise UploadError(502, "WeKnora 响应缺少 knowledge id")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    record = Upload(
        knowledge_id=knowledge_id,
        kb_id=kb_id,
        kb_name=kb["name"] if kb else "",
        uploader_user_id=uploader_user_id,
        uploader_username=uploader_username,
        uploader_organization=uploader_organization,
        file_name=file.filename or "untitled",
        file_type=ext,
        file_size=len(file_bytes),
        file_hash=str(weknora_resp.get("file_hash") or "").strip(),
        parse_status="pending",
        parse_error="",
        weknora_task_id=weknora_resp.get("task_id", ""),
        uploaded_at=now,
        last_synced_at=now,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
