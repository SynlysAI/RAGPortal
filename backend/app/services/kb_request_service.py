"""知识库申请与审批服务。"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import UserInfo
from app.models.kb_request import KbRequest

PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"


class KbRequestError(Exception):
    """知识库申请业务错误。"""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _serialize_request(request: KbRequest) -> dict[str, Any]:
    """序列化知识库申请记录。"""
    return {
        "id": request.id,
        "requester_user_id": request.requester_user_id,
        "requester_username": request.requester_username,
        "requester_organization": request.requester_organization,
        "requested_name": request.requested_name,
        "requested_description": request.requested_description,
        "request_reason": request.request_reason,
        "status": request.status,
        "reviewer_user_id": request.reviewer_user_id,
        "reviewer_username": request.reviewer_username,
        "review_reason": request.review_reason,
        "approved_kb_id": request.approved_kb_id,
        "approved_kb_name": request.approved_kb_name,
        "create_error": request.create_error,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


async def create_request(
    session: AsyncSession,
    user: UserInfo,
    requested_name: str,
    requested_description: str,
    request_reason: str,
) -> KbRequest:
    """创建一条新的知识库申请。"""
    name = requested_name.strip()
    if not name:
        raise KbRequestError(400, "知识库名称不能为空")
    result = await session.execute(
        select(KbRequest).where(
            KbRequest.requester_user_id == user.user_id,
            KbRequest.requested_name == name,
            KbRequest.status.in_((PENDING_STATUS, APPROVED_STATUS)),
        )
    )
    if result.scalars().first() is not None:
        raise KbRequestError(409, "已有同名申请正在处理中")
    now = _now_iso()
    record = KbRequest(
        requester_user_id=user.user_id,
        requester_username=user.username,
        requester_organization=user.organization,
        requested_name=name,
        requested_description=requested_description.strip(),
        request_reason=request_reason.strip(),
        status=PENDING_STATUS,
        created_at=now,
        updated_at=now,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def list_my_requests(
    session: AsyncSession,
    user: UserInfo,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """获取当前用户的知识库申请列表。"""
    base = select(KbRequest).where(KbRequest.requester_user_id == user.user_id)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = base.order_by(KbRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = [_serialize_request(item) for item in (await session.execute(stmt)).scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def list_requests(
    session: AsyncSession,
    page: int,
    page_size: int,
    status: str = "",
) -> dict[str, Any]:
    """管理员查看全部知识库申请。"""
    base = select(KbRequest)
    if status:
        base = base.where(KbRequest.status == status)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    stmt = base.order_by(KbRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = [_serialize_request(item) for item in (await session.execute(stmt)).scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def approve_request(
    session: AsyncSession,
    request_id: int,
    reviewer: UserInfo,
) -> dict[str, Any]:
    """批准申请，但不直接创建知识库。

    管理员需要在 WeKnora 中手工创建知识库并选择合适的模型参数，
    再让知识库列表自然出现在 RAGPortal 的可选范围内。
    """
    request = await session.get(KbRequest, request_id)
    if request is None:
        raise KbRequestError(404, "申请不存在")
    if request.status != PENDING_STATUS:
        raise KbRequestError(409, "当前状态不允许审批")

    now = _now_iso()
    request.status = APPROVED_STATUS
    request.reviewer_user_id = reviewer.user_id
    request.reviewer_username = reviewer.username
    request.review_reason = ""
    request.approved_kb_id = ""
    request.approved_kb_name = ""
    request.create_error = ""
    request.updated_at = now
    await session.commit()
    return _serialize_request(request)


async def reject_request(
    session: AsyncSession,
    request_id: int,
    reviewer: UserInfo,
    reason: str,
) -> dict[str, Any]:
    """驳回申请。"""
    request = await session.get(KbRequest, request_id)
    if request is None:
        raise KbRequestError(404, "申请不存在")
    if request.status != PENDING_STATUS:
        raise KbRequestError(409, "当前状态不允许驳回")
    request.status = REJECTED_STATUS
    request.reviewer_user_id = reviewer.user_id
    request.reviewer_username = reviewer.username
    request.review_reason = reason.strip()
    request.updated_at = _now_iso()
    await session.commit()
    return _serialize_request(request)
