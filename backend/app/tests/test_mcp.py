"""MCP Tool 权限和空间边界测试。"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.upload import Base, Upload
from app.services.mcp_service import call_tool, get_tool_definitions


def test_tool_definitions_only_include_granted_permissions():
    """Token 只看到已授权的 MCP Tool。"""
    tools = get_tool_definitions({"documents:search"})
    assert [tool["name"] for tool in tools] == ["rag_search"]


def test_search_rejects_unowned_knowledge_base():
    """用户没有上传记录的 KB 不允许检索。"""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(Upload(
                knowledge_id="k1", kb_id="owned", kb_name="Owned",
                uploader_user_id="u1", uploader_username="alice",
                file_name="a.md", file_type="md", file_size=1,
                uploaded_at="2026-09-24T00:00:00+00:00",
            ))
            await session.commit()
            try:
                await call_tool(
                    session=session,
                    user_id="u1",
                    tool_name="rag_search",
                    arguments={"query": "test", "kb_id": "other"},
                )
            except ValueError as exc:
                assert "无权" in str(exc)
            else:
                raise AssertionError("expected permission error")
        await engine.dispose()

    asyncio.run(run())
