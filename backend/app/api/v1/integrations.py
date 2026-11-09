"""内部系统集成接口。"""

import hashlib
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import UserInfo, get_current_user
from app.core.db import get_session
from app.core.weknora import WeknoraError, download_knowledge_file, get_knowledge
from app.models.upload import Upload


router = APIRouter(prefix="/api/integrations/research", tags=["integrations"])
PLANE_RESEARCH_SERVICE_USER_ID = "plane-research-bff"


@router.get("/files/{knowledge_id}")
async def download_research_file(
    knowledge_id: str,
    chain_id: str = Query(..., min_length=1),
    node_id: str = Query(..., min_length=1),
    kb_id: str = Query(..., min_length=1),
    file_hash: str = Query(..., pattern=r"^[0-9a-f]{64}$"),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """按 Plane 传入的研究链作用域代理一个 WeKnora 原文件。

    Args:
        knowledge_id: WeKnora 文档 ID。
        chain_id: Plane 研究链 ID；历史记录为空时以节点 ID 为权威。
        node_id: Plane 研究链节点 ID。
        kb_id: 已绑定的知识库 ID。
        file_hash: Plane 保存的小写 SHA-256 文件哈希。
        user: HMAC token 解析出的服务身份。
        session: 异步数据库会话。

    Returns:
        原文件字节响应。

    Raises:
        HTTPException: 服务身份、上传记录、作用域或上游文档校验失败。
    """
    if user.user_id != PLANE_RESEARCH_SERVICE_USER_ID or user.username != PLANE_RESEARCH_SERVICE_USER_ID:
        raise HTTPException(status_code=403, detail="仅允许 Plane 研究链服务访问")

    result = await session.execute(select(Upload).where(Upload.knowledge_id == knowledge_id))
    upload = result.scalars().first()
    scope_matched = upload is not None and (
        upload.kb_id == kb_id
        and upload.chain_node_id == node_id
        and (not upload.chain_id or upload.chain_id == chain_id)
    )
    if not scope_matched:
        raise HTTPException(status_code=404, detail="研究链资料不存在")

    try:
        knowledge = await get_knowledge(knowledge_id)
    except WeknoraError as exc:
        if exc.status == 404:
            raise HTTPException(status_code=404, detail="研究链资料不存在") from exc
        raise HTTPException(status_code=502, detail="文档服务暂不可用") from exc
    if knowledge.get("knowledge_base_id") != upload.kb_id:
        raise HTTPException(status_code=404, detail="研究链资料不存在")

    try:
        content, media_type = await download_knowledge_file(knowledge_id)
    except WeknoraError as exc:
        raise HTTPException(status_code=502, detail="原文件服务暂不可用") from exc
    stored_hash = upload.file_hash.strip().lower()
    source_is_valid = (
        len(content) == upload.file_size
        and hashlib.sha256(content).hexdigest() == file_hash
        and (
            hashlib.md5(content).hexdigest() == stored_hash
            if len(stored_hash) == 32
            else stored_hash == file_hash
        )
    )
    if not source_is_valid:
        raise HTTPException(status_code=502, detail="研究链原文件校验失败")
    filename = upload.file_name or knowledge.get("file_name") or knowledge_id
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename, safe='')}",
            "Cache-Control": "private, no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )
