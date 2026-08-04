"""知识库申请审批管理路由。"""
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import UserInfo, get_current_admin
from app.core.db import get_session
from app.services.kb_request_service import KbRequestError, approve_request, list_requests, reject_request

router = APIRouter(prefix="/api/admin/kb-requests", tags=["admin-kb-requests"])


class KbRequestRejectBody(BaseModel):
    """驳回知识库申请请求体。"""

    reason: str = Field(default="", max_length=2000)


@router.get("")
async def admin_list_kb_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query("", max_length=16),
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """管理员查看知识库申请列表。"""
    return await list_requests(session, page, page_size, status=status)


@router.post("/{request_id}/approve")
async def admin_approve_kb_request(
    request_id: int,
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """批准知识库申请。"""
    try:
        return await approve_request(session, request_id, admin)
    except KbRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/{request_id}/reject")
async def admin_reject_kb_request(
    request_id: int,
    body: KbRequestRejectBody,
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """驳回知识库申请。"""
    try:
        return await reject_request(session, request_id, admin, body.reason)
    except KbRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
