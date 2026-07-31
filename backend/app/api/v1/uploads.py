"""上传与个人历史路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user, UserInfo
from app.core.config import get_settings
from app.core.db import get_session
from app.models.upload import Upload
from app.services.sync_service import sync_one
from app.services.upload_service import UploadError, handle_upload

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _to_dict(u: Upload) -> dict:
    """序列化 Upload 为前端可读字典。"""
    return {
        "id": u.id,
        "knowledge_id": u.knowledge_id,
        "kb_id": u.kb_id,
        "kb_name": u.kb_name,
        "uploader_user_id": u.uploader_user_id,
        "uploader_username": u.uploader_username,
        "uploader_organization": u.uploader_organization,
        "file_name": u.file_name,
        "file_type": u.file_type,
        "file_size": u.file_size,
        "parse_status": u.parse_status,
        "parse_error": u.parse_error,
        "uploaded_at": u.uploaded_at,
    }


@router.post("")
async def upload(
    file: UploadFile = File(...),
    kb_id: str = Form(...),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """上传单个文件到指定 KB。"""
    settings = get_settings()
    try:
        record = await handle_upload(
            session=session,
            kb_id=kb_id,
            file=file,
            uploader_user_id=user.user_id,
            uploader_username=user.username,
            uploader_organization=user.organization,
            max_size_bytes=settings.upload_max_size_mb * 1024 * 1024,
            allowed_types=settings.allowed_file_types_set,
        )
    except UploadError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return _to_dict(record)


@router.get("/mine")
async def list_my_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """当前用户上传记录(按上传时间倒序)。"""
    offset = (page - 1) * page_size
    stmt = (
        select(Upload)
        .where(Upload.uploader_user_id == user.user_id)
        .order_by(Upload.uploaded_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    items = [_to_dict(u) for u in result.scalars().all()]
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/{upload_id}")
async def get_upload(
    upload_id: int,
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """单条记录详情(同时触发该记录的状态懒同步)。

    普通用户只能查自己的记录;admin 可查任何记录。
    """
    stmt = select(Upload).where(Upload.id == upload_id)
    if user.role != "admin":
        stmt = stmt.where(Upload.uploader_user_id == user.user_id)
    result = await session.execute(stmt)
    upload = result.scalars().first()
    if upload is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    await sync_one(session, upload)
    return _to_dict(upload)
