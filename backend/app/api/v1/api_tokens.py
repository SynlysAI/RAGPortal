"""账户级 API Token 管理路由。"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import UserInfo, get_current_user
from app.core.db import get_session
from app.models.api_token import ApiToken
from app.services.api_token_service import (
    ALL_PERMISSIONS,
    READ_PERMISSIONS,
    create_api_token,
    revoke_api_token,
)
from app.services.kb_service import get_kb_list

router = APIRouter(prefix="/api/api-tokens", tags=["api-tokens"])


class CreateTokenRequest(BaseModel):
    """创建 Token 请求。"""

    name: str = Field(min_length=1, max_length=128)
    permissions: list[str] = Field(default_factory=lambda: sorted(READ_PERMISSIONS))
    knowledge_base_ids: list[str] = Field(default_factory=list)
    expires_at: str = ""


def _to_dict(token: ApiToken) -> dict:
    """将 Token ORM 对象转换为不含明文的响应。"""
    return {
        "id": token.id,
        "name": token.name,
        "token_prefix": token.token_prefix,
        "permissions": json.loads(token.permissions_json or "[]"),
        "knowledge_base_ids": json.loads(token.knowledge_base_ids_json or "[]"),
        "status": token.status,
        "created_at": token.created_at,
        "expires_at": token.expires_at,
        "last_used_at": token.last_used_at,
        "revoked_at": token.revoked_at,
    }


@router.get("")
async def list_tokens(
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """列出当前账户创建的 API Token。"""
    result = await session.execute(
        select(ApiToken)
        .where(ApiToken.user_id == user.user_id)
        .order_by(ApiToken.id.desc())
    )
    return {"items": [_to_dict(token) for token in result.scalars().all()]}


@router.post("")
async def create_token(
    body: CreateTokenRequest,
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """创建 Token，并在响应中返回一次性明文。"""
    permissions = set(body.permissions)
    if not permissions <= ALL_PERMISSIONS:
        raise HTTPException(status_code=422, detail="包含不支持的 Token 权限")
    knowledge_base_ids = {kb_id.strip() for kb_id in body.knowledge_base_ids if kb_id.strip()}
    if not knowledge_base_ids:
        raise HTTPException(status_code=422, detail="至少绑定一个知识库")
    available_ids = {str(kb.get("id")) for kb in await get_kb_list()}
    if not knowledge_base_ids <= available_ids:
        raise HTTPException(status_code=422, detail="包含不存在或不可用的知识库")
    result = await create_api_token(
        session=session,
        user_id=user.user_id,
        username=user.username,
        name=body.name,
        permissions=permissions,
        knowledge_base_ids=knowledge_base_ids,
        expires_at=body.expires_at,
    )
    return {"token": _to_dict(result.token), "secret": result.secret}


@router.post("/{token_id}/revoke")
async def revoke_token(
    token_id: int,
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """撤销当前账户的 Token。"""
    if not await revoke_api_token(session, token_id, user.user_id):
        raise HTTPException(status_code=404, detail="Token 不存在")
    return {"ok": True}
