"""RAGPortal 远程 MCP Streamable HTTP 网关。"""

import json
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.weknora import WeknoraError, download_knowledge_file, get_knowledge
from app.services.api_token_service import verify_api_token
from app.services.download_ticket_service import resolve_download_ticket
from app.services.mcp_service import TOOL_PERMISSIONS, call_tool, get_tool_definitions
from app.services.mcp_images import search_image_blocks

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


async def _get_token(request: Request, session: AsyncSession):
    """从 Authorization 头解析并验证 RAGPortal API Token。"""
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要 RAGPortal API Token")
    token = await verify_api_token(session, authorization[7:].strip())
    if token is None:
        raise HTTPException(status_code=401, detail="Token 无效、已撤销或已过期")
    return token


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict:
    """构造 JSON-RPC 错误响应。"""
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


@router.post("")
async def mcp_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """处理 WorkBuddy 发来的 MCP JSON-RPC 请求。"""
    token = await _get_token(request, session)
    allowed_knowledge_base_ids = set(json.loads(token.knowledge_base_ids_json or "[]"))
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="请求体必须是 JSON") from exc
    request_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "RAGPortal", "version": "0.2.0"},
            },
        }
    if method == "tools/list":
        permissions = set(json.loads(token.permissions_json or "[]"))
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": get_tool_definitions(permissions)},
        }
    if method != "tools/call":
        return _jsonrpc_error(request_id, -32601, f"不支持的 MCP 方法: {method}")
    tool_name = str(params.get("name", ""))
    permission = TOOL_PERMISSIONS.get(tool_name)
    permissions = set(json.loads(token.permissions_json or "[]"))
    if permission is None:
        return _jsonrpc_error(request_id, -32601, f"未知 MCP Tool: {tool_name}")
    if permission not in permissions:
        return _jsonrpc_error(request_id, -32003, f"Token 没有权限: {permission}")
    try:
        result = await call_tool(
            session=session,
            user_id=token.user_id,
            tool_name=tool_name,
            arguments=params.get("arguments") or {},
            allowed_knowledge_base_ids=allowed_knowledge_base_ids,
            api_token_id=token.id,
        )
    except ValueError as exc:
        return _jsonrpc_error(request_id, -32602, str(exc))
    except Exception as exc:
        return _jsonrpc_error(request_id, -32000, f"Tool 执行失败: {exc}")
    content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
    if tool_name == "rag_search":
        content.extend(await search_image_blocks(result))
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": content,
            "structuredContent": result,
        },
    }


@router.get("/files/{document_id}")
async def download_file(
    document_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """验证下载权限后代理返回原始文件。"""
    token = await _get_token(request, session)
    authorization = request.headers.get("Authorization", "")
    if await verify_api_token(session, authorization[7:].strip(), "documents:download") is None:
        raise HTTPException(status_code=403, detail="Token 没有文件下载权限")
    knowledge = await get_knowledge(document_id)
    allowed_knowledge_base_ids = set(json.loads(token.knowledge_base_ids_json or "[]"))
    if knowledge.get("knowledge_base_id") not in allowed_knowledge_base_ids:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    return await _download_response(document_id, knowledge)


@router.get("/downloads/{ticket_secret}")
async def download_from_ticket(
    ticket_secret: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """使用短期凭证下载单个已授权文件，无需长期 API Token。

    Args:
        ticket_secret: 签发时返回的一次性明文凭证。
        session: 数据库会话。

    Returns:
        文档原始文件响应。
    """
    ticket = await resolve_download_ticket(session, ticket_secret)
    if ticket is None:
        raise HTTPException(status_code=404, detail="下载链接无效或已过期")
    try:
        knowledge = await get_knowledge(ticket.knowledge_id)
    except WeknoraError as exc:
        if exc.status == 404:
            raise HTTPException(status_code=404, detail="文档不存在") from exc
        raise HTTPException(status_code=502, detail="文档服务暂不可用") from exc
    if knowledge.get("knowledge_base_id") != ticket.kb_id:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    return await _download_response(ticket.knowledge_id, knowledge)


async def _download_response(document_id: str, knowledge: dict) -> Response:
    """代理 WeKnora 原文件并设置私密下载响应头。

    Args:
        document_id: WeKnora 文档 ID。
        knowledge: 已完成授权校验的 WeKnora 文档详情。

    Returns:
        带文件名和禁止缓存标记的二进制响应。
    """
    content, media_type = await download_knowledge_file(document_id)
    filename = knowledge.get("file_name") or knowledge.get("title") or document_id
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
            ),
            "Cache-Control": "private, no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )
