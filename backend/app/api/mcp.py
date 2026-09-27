"""RAGPortal 远程 MCP Streamable HTTP 网关。"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.weknora import download_knowledge_file
from app.models.upload import Upload
from app.services.api_token_service import verify_api_token
from app.services.mcp_service import TOOL_PERMISSIONS, call_tool, get_tool_definitions

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
        )
    except ValueError as exc:
        return _jsonrpc_error(request_id, -32602, str(exc))
    except Exception as exc:
        return _jsonrpc_error(request_id, -32000, f"Tool 执行失败: {exc}")
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            "structuredContent": result,
        },
    }


@router.get("/files/{document_id}")
async def download_file(
    document_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """验证下载权限后代理返回原始文件。"""
    token = await _get_token(request, session)
    authorization = request.headers.get("Authorization", "")
    if await verify_api_token(session, authorization[7:].strip(), "documents:download") is None:
        raise HTTPException(status_code=403, detail="Token 没有文件下载权限")
    result = await session.execute(
        select(Upload).where(
            Upload.id == document_id,
            Upload.uploader_user_id == token.user_id,
        )
    )
    upload = result.scalar_one_or_none()
    allowed_knowledge_base_ids = set(json.loads(token.knowledge_base_ids_json or "[]"))
    if upload is None or upload.kb_id not in allowed_knowledge_base_ids:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    content, media_type = await download_knowledge_file(upload.knowledge_id)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'},
    )
