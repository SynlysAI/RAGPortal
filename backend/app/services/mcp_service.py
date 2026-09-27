"""RAGPortal MCP Tool 业务服务。"""

import base64
import io
from typing import Any
from urllib.parse import urlsplit

import httpx

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.weknora import (
    WeknoraError, get_knowledge, list_knowledge_page, search_knowledge,
)
from app.services.kb_service import get_kb_list
from app.services.upload_service import handle_upload
from app.services.mcp_search_service import resolve_search_scope, search_libraries
from app.services.download_ticket_service import create_download_ticket

TOOL_PERMISSIONS = {
    "rag_list_knowledge_bases": "knowledge-bases:list",
    "rag_list_documents": "documents:list",
    "rag_search": "documents:search",
    "rag_get_document": "documents:read",
    "rag_download_file": "documents:download",
    "rag_upload_document": "documents:write",
}

TOOL_DEFINITIONS = [
    {
        "name": "rag_list_knowledge_bases",
        "description": "列出当前 API Token 绑定的知识库。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "rag_list_documents",
        "description": "列出 WeKnora 指定知识库中的全部文档。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kb_id": {"type": "string", "description": "知识库 ID"},
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["kb_id"],
        },
    },
    {
        "name": "rag_search",
        "description": "检索 Token 授权的知识库。不传范围时检索全部绑定库；可用 kb_id 或 kb_ids 指定范围，二者不可同时提供。top_k 为最终结果总数。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索问题"},
                "kb_id": {"type": "string", "description": "知识库 ID"},
                "kb_ids": {"type": "array", "items": {"type": "string"},
                           "minItems": 1, "description": "指定多个授权知识库 ID"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "rag_get_document",
        "description": "根据 WeKnora 文档 ID 获取文档详情。",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
        },
    },
    {
        "name": "rag_download_file",
        "description": "根据 WeKnora 文档 ID 签发十分钟有效的文件下载地址。",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
        },
    },
    {
        "name": "rag_upload_document",
        "description": "将 Base64 编码的文件写入指定知识库。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kb_id": {"type": "string"},
                "filename": {"type": "string"},
                "content_base64": {"type": "string"},
            },
            "required": ["kb_id", "filename", "content_base64"],
        },
    },
]


def get_tool_definitions(permissions: set[str]) -> list[dict[str, Any]]:
    """按 Token 权限过滤可见 Tool。"""
    return [
        definition
        for definition in TOOL_DEFINITIONS
        if TOOL_PERMISSIONS[definition["name"]] in permissions
    ]


def _public_download_base_url() -> str:
    """读取可信配置中的公网地址并禁止外网明文传输凭证。

    Returns:
        不带结尾斜杠的公网根地址。

    Raises:
        ValueError: 地址格式无效或外部链接未使用 HTTPS。
    """
    settings = get_settings()
    base_url = (settings.mcp_public_base_url or settings.frontend_origin).rstrip("/")
    parsed_url = urlsplit(base_url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ValueError("MCP_PUBLIC_BASE_URL 配置无效")
    is_local = parsed_url.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed_url.scheme != "https" and (
        not is_local or getattr(settings, "app_env", "development") == "production"
    ):
        raise ValueError("外部下载链接必须使用 HTTPS")
    return base_url


async def call_tool(
    *,
    session: AsyncSession,
    user_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    allowed_knowledge_base_ids: set[str] | None = None,
    api_token_id: int | None = None,
) -> dict[str, Any]:
    """执行已完成权限校验的 MCP Tool。

    Args:
        session: 数据库会话。
        user_id: Token 所属用户 ID。
        tool_name: 要执行的工具名称。
        arguments: 工具输入参数。
        allowed_knowledge_base_ids: Token 绑定的知识库 ID。
        api_token_id: 用于签发下载凭证的 API Token ID。

    Returns:
        工具的结构化执行结果。
    """
    allowed_ids = allowed_knowledge_base_ids or set()

    if tool_name == "rag_list_knowledge_bases":
        knowledge_bases = await get_kb_list()
        return {"items": [kb for kb in knowledge_bases if kb.get("id") in allowed_ids]}

    if tool_name == "rag_list_documents":
        kb_id = str(arguments.get("kb_id", "")).strip()
        if kb_id not in allowed_ids:
            raise ValueError("当前 Token 无权访问此知识库（未绑定）")
        page = arguments.get("page", 1)
        page_size = arguments.get("page_size", 20)
        if type(page) is not int or page < 1:
            raise ValueError("page 必须是正整数")
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("page_size 必须是 1 到 100 之间的整数")
        listing = await list_knowledge_page(kb_id, page=page, page_size=page_size)
        return {
            "items": [
                {
                    **item,
                    "document_id": item["id"],
                    "kb_id": kb_id,
                }
                for item in listing["items"]
            ],
            "page": listing["page"],
            "page_size": listing["page_size"],
            "total": listing["total"],
        }

    if tool_name in {"rag_get_document", "rag_download_file"}:
        document_id = arguments.get("document_id")
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id 必须是 WeKnora 文档 ID")
        knowledge = await get_knowledge(document_id.strip())
        kb_id = knowledge.get("knowledge_base_id")
        if kb_id not in allowed_ids:
            raise ValueError("文档不存在或无权访问")
        if tool_name == "rag_download_file":
            if api_token_id is None:
                raise ValueError("下载链接需要有效的 API Token")
            base_url = _public_download_base_url()
            ticket = await create_download_ticket(
                session, api_token_id, document_id.strip(), kb_id,
            )
            return {
                "document_id": document_id,
                "filename": knowledge.get("file_name") or knowledge.get("title"),
                "download_url": (
                    f"{base_url}/api/mcp/downloads/{ticket.secret}"
                ),
                "expires_at": ticket.expires_at.isoformat(),
            }
        return {
            "document_id": document_id,
            "kb_id": kb_id,
            "source": knowledge,
        }

    if tool_name == "rag_search":
        query = arguments.get("query", "")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query 必须是非空字符串")
        top_k = arguments.get("top_k", 5)
        if type(top_k) is not int or not 1 <= top_k <= 20:
            raise ValueError("top_k 必须是 1 到 20 之间的整数")
        kb_ids = resolve_search_scope(arguments, allowed_ids)
        try:
            names = {kb["id"]: kb.get("name") or kb["id"] for kb in await get_kb_list()}
        except (WeknoraError, httpx.HTTPError):
            names = {}
        return await search_libraries(
            query=query.strip(), kb_ids=kb_ids, top_k=top_k,
            names=names, search_one=search_knowledge,
        )

    if tool_name == "rag_upload_document":
        filename = str(arguments.get("filename", "untitled")).strip() or "untitled"
        kb_id = str(arguments.get("kb_id", "")).strip()
        try:
            content = base64.b64decode(str(arguments.get("content_base64", "")), validate=True)
        except Exception as exc:
            raise ValueError("content_base64 不是有效的 Base64") from exc
        if not kb_id or not content:
            raise ValueError("kb_id、filename 和 content_base64 不能为空")
        if kb_id not in allowed_ids:
            raise ValueError("当前 Token 无权访问此知识库（未绑定）")
        user = {
            "user_id": user_id,
            "username": user_id,
            "organization": "",
        }
        record = await handle_upload(
            session=session,
            kb_id=kb_id,
            file=UploadFile(file=io.BytesIO(content), filename=filename),
            uploader_user_id=user["user_id"],
            uploader_username=user["username"],
            uploader_organization=user["organization"],
            max_size_bytes=get_settings().upload_max_size_mb * 1024 * 1024,
            allowed_types=get_settings().allowed_file_types_set,
        )
        return {
            "document_id": record.knowledge_id,
            "knowledge_id": record.knowledge_id,
            "upload_id": record.id,
            "filename": record.file_name,
        }

    raise ValueError(f"未知 MCP Tool: {tool_name}")
