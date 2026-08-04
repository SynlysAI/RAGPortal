"""上传与个人历史路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user, UserInfo
from app.core.config import get_settings
from app.core.db import get_session
from app.models.upload import Upload
from app.services.ai4ms_user_service import find_ai4ms_user
from app.services.sync_service import sync_one, sync_pending
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
        "file_hash": u.file_hash,
        "parse_status": u.parse_status,
        "parse_error": u.parse_error,
        "uploaded_at": u.uploaded_at,
    }


async def _resolve_upload_user(
    *,
    request: Request,
    current_user: UserInfo,
    uploader_user_id: Optional[str],
) -> UserInfo:
    """解析本次上传应归属的用户。

    Args:
        request: 当前请求对象，用于透传 Authorization。
        current_user: 当前登录用户。
        uploader_user_id: 管理员指定的上传者 user_id。

    Returns:
        本次上传记录应使用的上传者信息。

    Raises:
        HTTPException: 非管理员指定上传者，或目标用户不存在。
    """
    target_user_id = (uploader_user_id or "").strip()
    if not target_user_id:
        return current_user
    if target_user_id == current_user.user_id:
        return current_user
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可以指定上传者")

    target_user = await find_ai4ms_user(
        request.headers.get("Authorization", ""),
        target_user_id,
    )
    if target_user is None:
        raise HTTPException(status_code=400, detail="指定上传者不存在")
    return target_user


@router.post("")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    kb_id: str = Form(...),
    uploader_user_id: Optional[str] = Form(None),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """上传单个文件到指定 KB。"""
    settings = get_settings()
    upload_user = await _resolve_upload_user(
        request=request,
        current_user=user,
        uploader_user_id=uploader_user_id,
    )
    try:
        record = await handle_upload(
            session=session,
            kb_id=kb_id,
            file=file,
            uploader_user_id=upload_user.user_id,
            uploader_username=upload_user.username,
            uploader_organization=upload_user.organization,
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
    """当前用户上传记录(按上传时间倒序)。

    每次拉取列表前先懒同步最近的 pending/processing 记录，
    让页面尽量展示 WeKnora 的最新解析状态。
    """
    await sync_pending(session)
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
