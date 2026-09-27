"""MCP 文件下载的知识库授权测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from app.api import mcp
from app.core.db import get_session
from app.models.api_token import ApiToken
from app.models.upload import Base
from app.services.download_ticket_service import create_download_ticket


def _request() -> Request:
    """构造带 API Token 的下载请求。"""
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/mcp/files/wk-1",
        "headers": [(b"authorization", b"Bearer test-token")],
    })


@pytest.mark.asyncio
async def test_download_rejects_document_outside_bound_library(monkeypatch):
    """WeKnora 中其他知识库的原始文件不能被当前 Token 下载。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    monkeypatch.setattr(mcp, "_get_token", AsyncMock(return_value=SimpleNamespace(
        knowledge_base_ids_json='["bound"]',
    )))
    monkeypatch.setattr(mcp, "verify_api_token", AsyncMock(return_value=True))
    monkeypatch.setattr(mcp, "get_knowledge", AsyncMock(return_value={
        "id": "wk-1", "knowledge_base_id": "other",
    }))
    download_mock = AsyncMock()
    monkeypatch.setattr(mcp, "download_knowledge_file", download_mock)

    with pytest.raises(HTTPException) as exc:
        await mcp.download_file("wk-1", _request(), None)

    assert exc.value.status_code == 404
    download_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_uses_weknora_document_id(monkeypatch):
    """授权后使用 WeKnora 文档 ID 下载原始文件。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    monkeypatch.setattr(mcp, "_get_token", AsyncMock(return_value=SimpleNamespace(
        knowledge_base_ids_json='["bound"]',
    )))
    monkeypatch.setattr(mcp, "verify_api_token", AsyncMock(return_value=True))
    monkeypatch.setattr(mcp, "get_knowledge", AsyncMock(return_value={
        "id": "wk-1", "knowledge_base_id": "bound", "file_name": "论文.pdf",
    }))
    download_mock = AsyncMock(return_value=(b"file", "application/pdf"))
    monkeypatch.setattr(mcp, "download_knowledge_file", download_mock)

    response = await mcp.download_file("wk-1", _request(), None)

    assert response.body == b"file"
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    download_mock.assert_awaited_once_with("wk-1")


@pytest.mark.asyncio
async def test_temporary_link_downloads_without_bearer_header(monkeypatch):
    """短期链接仅凭自身凭证完成校验和下载。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    ticket = SimpleNamespace(knowledge_id="wk-1", kb_id="bound")
    resolver = AsyncMock(return_value=ticket)
    monkeypatch.setattr(mcp, "resolve_download_ticket", resolver)
    monkeypatch.setattr(mcp, "get_knowledge", AsyncMock(return_value={
        "id": "wk-1", "knowledge_base_id": "bound", "file_name": "论文.pdf",
    }))
    monkeypatch.setattr(mcp, "download_knowledge_file", AsyncMock(
        return_value=(b"file", "application/pdf"),
    ))

    response = await mcp.download_from_ticket("rdl_temporary", None)

    assert response.body == b"file"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    resolver.assert_awaited_once_with(None, "rdl_temporary")


@pytest.mark.asyncio
async def test_temporary_link_rejects_changed_document_scope(monkeypatch):
    """文档被移到其他知识库后原下载链接失效。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    monkeypatch.setattr(mcp, "resolve_download_ticket", AsyncMock(
        return_value=SimpleNamespace(knowledge_id="wk-1", kb_id="bound"),
    ))
    monkeypatch.setattr(mcp, "get_knowledge", AsyncMock(return_value={
        "id": "wk-1", "knowledge_base_id": "other",
    }))
    download_mock = AsyncMock()
    monkeypatch.setattr(mcp, "download_knowledge_file", download_mock)

    with pytest.raises(HTTPException) as exc:
        await mcp.download_from_ticket("rdl_temporary", None)

    assert exc.value.status_code == 404
    download_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_temporary_link_rejects_expired_ticket_before_upstream_call(monkeypatch):
    """无效下载凭证不触发 WeKnora 请求。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    monkeypatch.setattr(mcp, "resolve_download_ticket", AsyncMock(return_value=None))
    detail_mock = AsyncMock()
    monkeypatch.setattr(mcp, "get_knowledge", detail_mock)

    with pytest.raises(HTTPException) as exc:
        await mcp.download_from_ticket("rdl_expired", None)

    assert exc.value.status_code == 404
    detail_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_link_works_without_header_then_stops_after_revocation(monkeypatch):
    """实际 HTTP 下载无需 Bearer，撤销原 Token 后立即返回 404。

    Args:
        monkeypatch: pytest 注入替换工具。
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        token = ApiToken(
            user_id="u1", username="alice", name="下载测试",
            token_prefix="rpt_test", token_hash="a" * 64,
            permissions_json='["documents:download"]',
            knowledge_base_ids_json='["kb-a"]', status="active",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)
        ticket = await create_download_ticket(session, token.id, "wk-1", "kb-a")
        token_id = token.id

    async def session_dependency():
        """提供测试数据库会话。"""
        async with session_factory() as session:
            yield session

    app = FastAPI()
    app.include_router(mcp.router)
    app.dependency_overrides[get_session] = session_dependency
    monkeypatch.setattr(mcp, "get_knowledge", AsyncMock(return_value={
        "id": "wk-1", "knowledge_base_id": "kb-a", "file_name": "论文.pdf",
    }))
    monkeypatch.setattr(mcp, "download_knowledge_file", AsyncMock(
        return_value=(b"pdf", "application/pdf"),
    ))
    url = f"/api/mcp/downloads/{ticket.secret}"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
    ) as client:
        response = await client.get(url)
        assert response.status_code == 200
        assert response.content == b"pdf"
        response = await client.get(url)
        assert response.status_code == 200
        async with session_factory() as session:
            stored_token = await session.get(ApiToken, token_id)
            stored_token.status = "revoked"
            await session.commit()
        response = await client.get(url)
        assert response.status_code == 404

    await engine.dispose()
