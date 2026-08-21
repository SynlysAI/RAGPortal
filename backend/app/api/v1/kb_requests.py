"""知识库申请路由。"""
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import UserInfo, get_current_user
from app.core.db import get_session
from app.services.kb_request_service import KbRequestError, create_request, list_my_requests

router = APIRouter(prefix="/api/kb-requests", tags=["kb-requests"])


class KbRequestCreateBody(BaseModel):
    """创建知识库申请请求体。"""

    requested_name: str = Field(min_length=1, max_length=255)
    requested_description: str = ""
    request_reason: str = ""
    want_wiki: bool = False
    want_llm_graph: bool = False
    extract_focus: str = ""
    relation_types: str = ""
    example_text: str = ""


@router.post("")
async def submit_kb_request(
    body: KbRequestCreateBody,
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """提交知识库申请。"""
    try:
        record = await create_request(
            session,
            user,
            body.requested_name,
            body.requested_description,
            body.request_reason,
            body.want_wiki,
            body.want_llm_graph,
            body.extract_focus,
            body.relation_types,
            body.example_text,
        )
    except KbRequestError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return {
        "id": record.id,
        "requester_user_id": record.requester_user_id,
        "requester_username": record.requester_username,
        "requester_organization": record.requester_organization,
        "requested_name": record.requested_name,
        "requested_description": record.requested_description,
        "request_reason": record.request_reason,
        "want_wiki": bool(record.want_wiki),
        "want_llm_graph": bool(record.want_llm_graph),
        "extract_focus": record.extract_focus,
        "relation_types": record.relation_types,
        "example_text": record.example_text,
        "status": record.status,
        "reviewer_user_id": record.reviewer_user_id,
        "reviewer_username": record.reviewer_username,
        "review_reason": record.review_reason,
        "approved_kb_id": record.approved_kb_id,
        "approved_kb_name": record.approved_kb_name,
        "create_error": record.create_error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@router.get("/mine")
async def my_kb_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """获取我的知识库申请列表。"""
    return await list_my_requests(session, user, page, page_size)
