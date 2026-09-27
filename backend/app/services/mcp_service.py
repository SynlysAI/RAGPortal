"""RAGPortal MCP Tool 业务服务。"""

import base64
import io
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.weknora import get_knowledge, search_knowledge
from app.services.kb_service import get_kb_list
from app.models.upload import Upload
from app.services.upload_service import handle_upload

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
        "description": "列出当前账户在指定知识库的上传记录。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kb_id": {"type": "string", "description": "知识库 ID"},
            },
            "required": ["kb_id"],
        },
    },
    {
        "name": "rag_search",
        "description": "在指定 WeKnora 知识库中检索文档。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索问题"},
                "kb_id": {"type": "string", "description": "知识库 ID"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query", "kb_id"],
        },
    },
    {
        "name": "rag_get_document",
        "description": "获取一篇文档的元数据和 WeKnora 状态。",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": {"type": "integer"}},
            "required": ["document_id"],
        },
    },
    {
        "name": "rag_download_file",
        "description": "获取文档原始文件的受控下载地址或元数据。",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": {"type": "integer"}},
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


async def call_tool(
    *,
    session: AsyncSession,
    user_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    allowed_knowledge_base_ids: set[str] | None = None,
) -> dict[str, Any]:
    """执行一个已完成权限校验的 MCP Tool。"""
    allowed_ids = allowed_knowledge_base_ids or set()

    if tool_name == "rag_list_knowledge_bases":
        knowledge_bases = await get_kb_list()
        return {"items": [kb for kb in knowledge_bases if kb.get("id") in allowed_ids]}

    if tool_name == "rag_list_documents":
        kb_id = str(arguments.get("kb_id", "")).strip()
        if kb_id not in allowed_ids:
            raise ValueError("当前 Token 无权访问此知识库（未绑定）")
        result = await session.execute(
            select(Upload)
            .where(Upload.uploader_user_id == user_id, Upload.kb_id == kb_id)
            .order_by(Upload.uploaded_at.desc())
            .limit(100)
        )
        return {
            "items": [
                {
                    "document_id": item.id,
                    "knowledge_id": item.knowledge_id,
                    "kb_id": item.kb_id,
                    "title": item.file_name,
                    "path": item.file_name,
                    "file_type": item.file_type,
                    "parse_status": item.parse_status,
                    "updated_at": item.uploaded_at,
                }
                for item in result.scalars().all()
            ]
        }

    if tool_name in {"rag_get_document", "rag_download_file"}:
        document_id = int(arguments.get("document_id", 0))
        result = await session.execute(
            select(Upload).where(
                Upload.id == document_id,
                Upload.uploader_user_id == user_id,
            )
        )
        upload = result.scalar_one_or_none()
        if upload is None or upload.kb_id not in allowed_ids:
            raise ValueError("文档不存在或无权访问")
        if tool_name == "rag_download_file":
            return {
                "document_id": upload.id,
                "filename": upload.file_name,
                "download_url": f"/api/mcp/files/{upload.id}",
                "message": "请使用同一 Bearer Token 访问 download_url。",
            }
        knowledge = await get_knowledge(upload.knowledge_id)
        return {
            "document_id": upload.id,
            "knowledge_id": upload.knowledge_id,
            "title": upload.file_name,
            "path": upload.file_name,
            "kb_id": upload.kb_id,
            "parse_status": upload.parse_status,
            "uploaded_at": upload.uploaded_at,
            "source": knowledge,
        }

    if tool_name == "rag_search":
        query = str(arguments.get("query", "")).strip()
        kb_id = str(arguments.get("kb_id", "")).strip()
        if not query or not kb_id:
            raise ValueError("query 和 kb_id 不能为空")
        if kb_id not in allowed_ids:
            raise ValueError("当前 Token 无权访问此知识库（未绑定）")
        return await search_knowledge(
            kb_id=kb_id,
            query=query,
            top_k=int(arguments.get("top_k", 5)),
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
            "document_id": record.id,
            "knowledge_id": record.knowledge_id,
            "filename": record.file_name,
        }

    raise ValueError(f"未知 MCP Tool: {tool_name}")
