"""Admin 路由:全部上传记录 / 导出 CSV / 统计。"""
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_admin, get_current_user, UserInfo
from app.core.db import get_session
from app.models.upload import Upload
from app.services.ai4ms_user_service import list_ai4ms_users
from app.services.backfill_service import backfill_uploads_from_weknora
from app.services.sync_service import sync_pending

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _user_to_dict(user: UserInfo) -> dict:
    """序列化用户信息。

    Args:
        user: 用户信息对象。

    Returns:
        前端可读的用户字典。
    """
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "organization": user.organization,
    }


def _to_admin_dict(u: Upload) -> dict:
    """admin 视角的记录序列化(含上传者完整信息)。"""
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


@router.get("/users")
async def list_users(
    request: Request,
    admin: UserInfo = Depends(get_current_admin),
) -> list[dict]:
    """代理获取 AI4MS 用户列表。

    Args:
        request: 当前请求对象，用于透传 Authorization。
        admin: 当前管理员用户。

    Returns:
        AI4MS 用户列表。
    """
    users = await list_ai4ms_users(request.headers.get("Authorization", ""))
    return [_user_to_dict(user) for user in users]


def _apply_filters(
    stmt,
    uploader: Optional[str],
    kb_id: Optional[str],
    status: Optional[str],
    filename: Optional[str],
    start: Optional[str],
    end: Optional[str],
):
    """应用筛选条件到 select 语句。"""
    if uploader:
        stmt = stmt.where(Upload.uploader_username.like(f"%{uploader}%"))
    if kb_id:
        stmt = stmt.where(Upload.kb_id == kb_id)
    if status:
        stmt = stmt.where(Upload.parse_status == status)
    if filename:
        stmt = stmt.where(Upload.file_name.like(f"%{filename}%"))
    if start:
        stmt = stmt.where(Upload.uploaded_at >= start)
    if end:
        stmt = stmt.where(Upload.uploaded_at <= end)
    return stmt


@router.get("/uploads")
async def list_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    uploader: Optional[str] = Query(None),
    kb_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    filename: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """全部上传记录只读列表(支持筛选与分页)。"""
    base = _apply_filters(select(Upload), uploader, kb_id, status, filename, start, end)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = base.order_by(Upload.uploaded_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = [_to_admin_dict(u) for u in (await session.execute(stmt)).scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/uploads/export")
async def export_uploads(
    uploader: Optional[str] = Query(None),
    kb_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    filename: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """按当前筛选条件导出 CSV。"""
    stmt = _apply_filters(select(Upload), uploader, kb_id, status, filename, start, end)
    stmt = stmt.order_by(Upload.uploaded_at.desc())
    rows = (await session.execute(stmt)).scalars().all()

    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM,Excel 中文兼容
    writer = csv.writer(buf)
    writer.writerow([
        "上传者用户名", "组织", "文件名", "知识库", "文件大小(字节)",
        "状态", "失败原因", "上传时间", "WeKnora 文档 ID",
    ])
    for u in rows:
        writer.writerow([
            u.uploader_username, u.uploader_organization, u.file_name,
            u.kb_name, u.file_size, u.parse_status, u.parse_error,
            u.uploaded_at, u.knowledge_id,
        ])
    buf.seek(0)
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=uploads_{now}.csv"},
    )


@router.post("/uploads/sync-status")
async def sync_status(
    limit: int = Query(50, ge=1, le=500),
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """触发批量懒同步(对最近 N 条非终态记录)。"""
    n = await sync_pending(session, limit=limit)
    return {"synced": n}


@router.post("/uploads/backfill")
async def backfill_uploads(
    page_size: int = Query(100, ge=1, le=200),
    max_pages_per_kb: int = Query(100, ge=1, le=1000),
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """从 WeKnora 历史知识回写本地上传记录。

    Args:
        page_size: 每页拉取数量。
        max_pages_per_kb: 每个知识库最多扫描页数。
        admin: 当前管理员用户。
        session: 数据库会话。

    Returns:
        回写统计信息。
    """
    return await backfill_uploads_from_weknora(
        session,
        page_size=page_size,
        max_pages_per_kb=max_pages_per_kb,
    )


@router.get("/stats/overview")
async def stats_overview(
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """仪表盘 KPI。"""
    total = (await session.execute(select(func.count(Upload.id)))).scalar_one()
    week_ago_iso = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    week_count = (await session.execute(
        select(func.count(Upload.id)).where(Upload.uploaded_at >= week_ago_iso)
    )).scalar_one()
    failed = (await session.execute(
        select(func.count(Upload.id)).where(Upload.parse_status == "failed")
    )).scalar_one()
    active_users = (await session.execute(
        select(func.count(func.distinct(Upload.uploader_user_id)))
        .where(Upload.uploaded_at >= week_ago_iso)
    )).scalar_one()
    return {
        "total": total,
        "week_count": week_count,
        "failed": failed,
        "active_users_7d": active_users,
    }


@router.get("/stats/daily-trend")
async def stats_daily_trend(
    days: int = Query(30, ge=1, le=365),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """近 N 天每日上传量。"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    stmt = (
        select(Upload.uploaded_at)
        .where(Upload.uploaded_at >= since)
        .order_by(Upload.uploaded_at.asc())
    )
    timestamps = (await session.execute(stmt)).scalars().all()
    buckets: dict[str, int] = {}
    for ts in timestamps:
        day = ts[:10]
        buckets[day] = buckets.get(day, 0) + 1
    return {"items": [{"date": d, "count": c} for d, c in sorted(buckets.items())]}


@router.get("/stats/top-uploaders")
async def stats_top_uploaders(
    n: int = Query(5, ge=1, le=50),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Top N 上传者。"""
    stmt = (
        select(
            Upload.uploader_user_id,
            Upload.uploader_username,
            func.count(Upload.id).label("cnt"),
        )
        .group_by(Upload.uploader_user_id, Upload.uploader_username)
        .order_by(func.count(Upload.id).desc())
        .limit(n)
    )
    rows = (await session.execute(stmt)).all()
    return {"items": [{"user_id": r[0], "username": r[1], "count": r[2]} for r in rows]}


@router.get("/stats/user-kb-distribution")
async def stats_user_kb_distribution(
    user_id: str = Query(..., min_length=1),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """指定上传者在各知识库的上传分布。

    Args:
        user_id: 上传者 user_id。
        user: 当前登录用户。
        session: 数据库会话。

    Returns:
        知识库上传数量排行。
    """
    stmt = (
        select(Upload.kb_id, Upload.kb_name, func.count(Upload.id).label("cnt"))
        .where(Upload.uploader_user_id == user_id)
        .group_by(Upload.kb_id, Upload.kb_name)
        .order_by(func.count(Upload.id).desc())
    )
    rows = (await session.execute(stmt)).all()
    return {"items": [{"kb_id": r[0], "kb_name": r[1], "count": r[2]} for r in rows]}


@router.get("/stats/kb-uploaders")
async def stats_kb_uploaders(
    kb_id: str = Query(..., min_length=1),
    n: int = Query(50, ge=1, le=200),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """指定知识库下的上传者排行。

    Args:
        kb_id: 知识库 ID。
        n: 返回排行数量。
        user: 当前登录用户。
        session: 数据库会话。

    Returns:
        上传者上传数量排行。
    """
    stmt = (
        select(
            Upload.uploader_user_id,
            Upload.uploader_username,
            func.count(Upload.id).label("cnt"),
        )
        .where(Upload.kb_id == kb_id)
        .group_by(Upload.uploader_user_id, Upload.uploader_username)
        .order_by(func.count(Upload.id).desc())
        .limit(n)
    )
    rows = (await session.execute(stmt)).all()
    return {"items": [{"user_id": r[0], "username": r[1], "count": r[2]} for r in rows]}


@router.get("/stats/kb-distribution")
async def stats_kb_distribution(
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """各 KB 上传分布。"""
    stmt = (
        select(Upload.kb_id, Upload.kb_name, func.count(Upload.id).label("cnt"))
        .group_by(Upload.kb_id, Upload.kb_name)
        .order_by(func.count(Upload.id).desc())
    )
    rows = (await session.execute(stmt)).all()
    return {"items": [{"kb_id": r[0], "kb_name": r[1], "count": r[2]} for r in rows]}
