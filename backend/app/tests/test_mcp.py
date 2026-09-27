"""MCP Tool 权限和空间边界测试。"""

import asyncio
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.upload import Base, Upload
from app.services.mcp_service import call_tool, get_tool_definitions
from app.services import mcp_service


def test_tool_definitions_only_include_granted_permissions():
    """Token 只看到已授权的 MCP Tool。"""
    tools = get_tool_definitions({"documents:search"})
    assert [tool["name"] for tool in tools] == ["rag_search"]


def test_knowledge_base_tool_requires_list_permission():
    """知识库列表 Tool 受独立权限控制。"""
    assert get_tool_definitions({"knowledge-bases:list"})[0]["name"] == "rag_list_knowledge_bases"


def test_knowledge_base_list_only_returns_bound_items(monkeypatch):
    """客户端只能发现 Token 绑定的知识库。"""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            monkeypatch.setattr(
                mcp_service,
                "get_kb_list",
                AsyncMock(return_value=[
                    {"id": "bound", "name": "授权库"},
                    {"id": "other", "name": "其他库"},
                ]),
            )
            result = await call_tool(
                session=session,
                user_id="u1",
                tool_name="rag_list_knowledge_bases",
                arguments={},
                allowed_knowledge_base_ids={"bound"},
            )
            assert result == {"items": [{"id": "bound", "name": "授权库"}]}
        await engine.dispose()

    asyncio.run(run())


def test_search_accepts_bound_knowledge_base_without_prior_upload(monkeypatch):
    """Token 绑定知识库后无需先有个人上传记录即可检索。"""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            search_mock = AsyncMock(return_value={"items": []})
            monkeypatch.setattr(mcp_service, "search_knowledge", search_mock)
            result = await call_tool(
                session=session,
                user_id="u1",
                tool_name="rag_search",
                arguments={"query": "test", "kb_id": "bound"},
                allowed_knowledge_base_ids={"bound"},
            )
            assert result == {"items": []}
            search_mock.assert_awaited_once()
        await engine.dispose()

    asyncio.run(run())


def test_search_rejects_unbound_knowledge_base():
    """Token 未绑定指定 KB 时检索被拒绝。"""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await call_tool(
                    session=session,
                    user_id="u1",
                    tool_name="rag_search",
                    arguments={"query": "test", "kb_id": "other"},
                    allowed_knowledge_base_ids={"bound"},
                )
            except ValueError as exc:
                assert "无权" in str(exc)
            else:
                raise AssertionError("expected permission error")
        await engine.dispose()

    asyncio.run(run())


def test_list_documents_returns_local_ids_only_in_bound_knowledge_base():
    """文档列表返回可供读取工具继续使用的本地 ID。"""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add_all([
                Upload(
                    knowledge_id="k1", kb_id="bound", kb_name="授权库",
                    uploader_user_id="u1", uploader_username="alice",
                    file_name="a.md", file_type="md", file_size=1,
                    uploaded_at="2026-09-24T00:00:00+00:00",
                ),
                Upload(
                    knowledge_id="k2", kb_id="bound", kb_name="授权库",
                    uploader_user_id="u2", uploader_username="bob",
                    file_name="b.md", file_type="md", file_size=1,
                    uploaded_at="2026-09-24T00:00:00+00:00",
                ),
            ])
            await session.commit()
            result = await call_tool(
                session=session,
                user_id="u1",
                tool_name="rag_list_documents",
                arguments={"kb_id": "bound"},
                allowed_knowledge_base_ids={"bound"},
            )
            assert len(result["items"]) == 1
            assert result["items"][0]["knowledge_id"] == "k1"
            assert isinstance(result["items"][0]["document_id"], int)
        await engine.dispose()

    asyncio.run(run())
