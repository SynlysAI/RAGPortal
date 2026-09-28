"""MCP Tool 权限和空间边界测试。"""

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.weknora import WeknoraError
from app.models.upload import Base, Upload
from app.services.mcp_service import call_tool, get_tool_definitions
from app.services import mcp_service


def test_tool_definitions_only_include_granted_permissions():
    """Token 只看到已授权的 MCP Tool。"""
    tools = get_tool_definitions({"documents:search"})
    assert [tool["name"] for tool in tools] == ["rag_search"]


def test_search_tool_declares_output_schema():
    """检索 Tool 声明结构化输出，便于客户端解析 structuredContent。"""
    tool = get_tool_definitions({"documents:search"})[0]
    assert tool["outputSchema"]["type"] == "object"
    assert set(tool["outputSchema"]["required"]) == {
        "items", "kb_ids", "partial", "errors", "ranking",
    }


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
            monkeypatch.setattr(mcp_service, "get_kb_list", AsyncMock(return_value=[]))
            result = await call_tool(
                session=session,
                user_id="u1",
                tool_name="rag_search",
                arguments={"query": "test", "kb_id": "bound"},
                allowed_knowledge_base_ids={"bound"},
            )
            assert result["items"] == []
            assert result["kb_ids"] == ["bound"]
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


def test_list_documents_uses_weknora_and_returns_knowledge_ids(monkeypatch):
    """文档列表包括直接写入 WeKnora 的文档，返回可继续读取的 ID。"""
    list_mock = AsyncMock(return_value={
        "items": [{"id": "wk-1", "knowledge_base_id": "bound", "title": "论文"}],
        "page": 1, "page_size": 20, "total": 1,
    })
    monkeypatch.setattr(mcp_service, "list_knowledge_page", list_mock)
    result = asyncio.run(call_tool(
        session=None, user_id="u1", tool_name="rag_list_documents",
        arguments={"kb_id": "bound", "page": 1, "page_size": 20},
        allowed_knowledge_base_ids={"bound"},
    ))
    list_mock.assert_awaited_once_with("bound", page=1, page_size=20)
    assert result["items"][0]["document_id"] == "wk-1"


def test_list_documents_rejects_unbound_library_before_upstream_call(monkeypatch):
    """Token 未绑定的知识库不会触发上游文档列表查询。"""
    list_mock = AsyncMock()
    monkeypatch.setattr(mcp_service, "list_knowledge_page", list_mock)
    try:
        asyncio.run(call_tool(
            session=None, user_id="u1", tool_name="rag_list_documents",
            arguments={"kb_id": "other"},
            allowed_knowledge_base_ids={"bound"},
        ))
    except ValueError as exc:
        assert "无权" in str(exc)
    else:
        raise AssertionError("应拒绝未绑定知识库")
    list_mock.assert_not_awaited()


def test_get_document_checks_weknora_knowledge_base(monkeypatch):
    """详情根据 WeKnora 的归属知识库做 Token 权限校验。"""
    detail_mock = AsyncMock(return_value={
        "id": "wk-1", "knowledge_base_id": "other", "title": "私有论文",
    })
    monkeypatch.setattr(mcp_service, "get_knowledge", detail_mock)
    try:
        asyncio.run(call_tool(
            session=None, user_id="u1", tool_name="rag_get_document",
            arguments={"document_id": "wk-1"}, allowed_knowledge_base_ids={"bound"},
        ))
    except ValueError as exc:
        assert "无权" in str(exc)
    else:
        raise AssertionError("应拒绝未绑定的文档")


def test_get_document_accepts_weknora_document_without_local_upload(monkeypatch):
    """被绑定库中的 WeKnora 文档不依赖门户上传记录。"""
    monkeypatch.setattr(mcp_service, "get_knowledge", AsyncMock(return_value={
        "id": "wk-1", "knowledge_base_id": "bound", "title": "论文",
    }))
    result = asyncio.run(call_tool(
        session=None, user_id="u1", tool_name="rag_get_document",
        arguments={"document_id": "wk-1"},
        allowed_knowledge_base_ids={"bound"},
    ))
    assert result["document_id"] == "wk-1"
    assert result["source"]["title"] == "论文"


def test_upload_returns_weknora_document_id_and_separate_upload_id(monkeypatch):
    """上传结果的 document_id 能直接用于文档读取和下载。"""
    upload_mock = AsyncMock(return_value=SimpleNamespace(
        id=42,
        knowledge_id="wk-1",
        file_name="论文.pdf",
    ))
    monkeypatch.setattr(mcp_service, "handle_upload", upload_mock)
    result = asyncio.run(call_tool(
        session=None,
        user_id="u1",
        tool_name="rag_upload_document",
        arguments={
            "kb_id": "bound",
            "filename": "论文.pdf",
            "content_base64": base64.b64encode(b"pdf").decode("ascii"),
        },
        allowed_knowledge_base_ids={"bound"},
    ))
    assert result == {
        "document_id": "wk-1",
        "knowledge_id": "wk-1",
        "upload_id": 42,
        "filename": "论文.pdf",
    }


def test_upload_status_tool_is_available_with_write_permission():
    """仅有写权限的 Token 也能查询自己上传文档的处理状态。"""
    names = [tool["name"] for tool in get_tool_definitions({"documents:write"})]
    assert names == ["rag_upload_document", "rag_get_upload_status"]


def test_upload_status_reads_current_weknora_state(monkeypatch):
    """查询本人上传记录时返回 WeKnora 的实时解析和启用状态。

    Args:
        monkeypatch: 替换 WeKnora 详情请求。
    """
    async def run():
        """在临时数据库中执行状态查询。"""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(Upload(
                knowledge_id="wk-1", kb_id="bound", kb_name="授权库",
                uploader_user_id="u1", uploader_username="用户",
                file_name="论文.pdf", file_type="pdf", file_size=3,
                uploaded_at="2026-09-28T00:00:00+00:00",
            ))
            await session.commit()
            detail_mock = AsyncMock(return_value={
                "id": "wk-1", "knowledge_base_id": "bound",
                "parse_status": "finalizing", "enable_status": "disabled",
                "error_message": "",
            })
            monkeypatch.setattr(mcp_service, "get_knowledge", detail_mock)
            result = await call_tool(
                session=session, user_id="u1", tool_name="rag_get_upload_status",
                arguments={"document_id": "wk-1"},
                allowed_knowledge_base_ids={"bound"},
            )
            assert result["document_id"] == "wk-1"
            assert result["upload_id"] == 1
            assert result["parse_status"] == "finalizing"
            assert result["enable_status"] == "disabled"
            assert result["error_message"] == ""
            assert result["checked_at"]
            detail_mock.assert_awaited_once_with("wk-1")
            detail_mock.return_value = {
                "id": "wk-1", "knowledge_base_id": "bound",
                "parse_status": "cancelled", "enable_status": "disabled",
                "error_message": "用户已取消解析",
            }
            cancelled = await call_tool(
                session=session, user_id="u1", tool_name="rag_get_upload_status",
                arguments={"document_id": "wk-1"},
                allowed_knowledge_base_ids={"bound"},
            )
            assert cancelled["parse_status"] == "cancelled"
            assert cancelled["error_message"] == "用户已取消解析"
            detail_mock.side_effect = WeknoraError(404, "文档不存在")
            deleted = await call_tool(
                session=session, user_id="u1", tool_name="rag_get_upload_status",
                arguments={"document_id": "wk-1"},
                allowed_knowledge_base_ids={"bound"},
            )
            assert deleted["parse_status"] == "deleted"
        await engine.dispose()

    asyncio.run(run())


def test_upload_status_rejects_other_users_before_upstream_call(monkeypatch):
    """即使文档在绑定库中，也不能查询其他用户的上传状态。

    Args:
        monkeypatch: 监测是否访问 WeKnora。
    """
    async def run():
        """在临时数据库中验证上传者隔离。"""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(Upload(
                knowledge_id="wk-1", kb_id="bound", kb_name="授权库",
                uploader_user_id="u2", uploader_username="其他用户",
                file_name="论文.pdf", file_type="pdf", file_size=3,
                uploaded_at="2026-09-28T00:00:00+00:00",
            ))
            await session.commit()
            detail_mock = AsyncMock()
            monkeypatch.setattr(mcp_service, "get_knowledge", detail_mock)
            try:
                await call_tool(
                    session=session, user_id="u1", tool_name="rag_get_upload_status",
                    arguments={"document_id": "wk-1"},
                    allowed_knowledge_base_ids={"bound"},
                )
            except ValueError as exc:
                assert "无权" in str(exc)
            else:
                raise AssertionError("应拒绝查询其他用户的上传记录")
            detail_mock.assert_not_awaited()
        await engine.dispose()

    asyncio.run(run())


def test_upload_status_rejects_unbound_knowledge_base(monkeypatch):
    """Token 解绑知识库后不能继续查询该库中的上传状态。

    Args:
        monkeypatch: 监测是否访问 WeKnora。
    """
    async def run():
        """在临时数据库中验证知识库绑定。"""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(Upload(
                knowledge_id="wk-1", kb_id="other", kb_name="未授权库",
                uploader_user_id="u1", uploader_username="用户",
                file_name="论文.pdf", file_type="pdf", file_size=3,
                uploaded_at="2026-09-28T00:00:00+00:00",
            ))
            await session.commit()
            detail_mock = AsyncMock()
            monkeypatch.setattr(mcp_service, "get_knowledge", detail_mock)
            try:
                await call_tool(
                    session=session, user_id="u1", tool_name="rag_get_upload_status",
                    arguments={"document_id": "wk-1"},
                    allowed_knowledge_base_ids={"bound"},
                )
            except ValueError as exc:
                assert "无权" in str(exc)
            else:
                raise AssertionError("应拒绝查询未绑定知识库的上传状态")
            detail_mock.assert_not_awaited()
        await engine.dispose()

    asyncio.run(run())


def test_download_tool_returns_short_lived_public_link(monkeypatch):
    """下载工具签发无需暴露长期 API Token 的完整地址。"""
    monkeypatch.setattr(mcp_service, "get_knowledge", AsyncMock(return_value={
        "id": "wk-1", "knowledge_base_id": "bound", "file_name": "论文.pdf",
    }))
    issue_mock = AsyncMock(return_value=SimpleNamespace(
        secret="rdl_temporary",
        expires_at=datetime(2026, 9, 27, 7, 0, tzinfo=timezone.utc),
    ))
    monkeypatch.setattr(mcp_service, "create_download_ticket", issue_mock)
    monkeypatch.setattr(mcp_service, "get_settings", lambda: SimpleNamespace(
        mcp_public_base_url="https://rag.example.com",
        frontend_origin="http://localhost:3002",
    ))

    result = asyncio.run(call_tool(
        session=None, user_id="u1", tool_name="rag_download_file",
        arguments={"document_id": "wk-1"},
        allowed_knowledge_base_ids={"bound"}, api_token_id=7,
    ))

    assert result["download_url"] == (
        "https://rag.example.com/api/mcp/downloads/rdl_temporary"
    )
    assert result["expires_at"] == "2026-09-27T07:00:00+00:00"
    issue_mock.assert_awaited_once_with(None, 7, "wk-1", "bound")


def test_download_tool_rejects_http_public_url_in_production_before_minting(monkeypatch):
    """生产环境的非 HTTPS 配置不能签发下载凭证。"""
    monkeypatch.setattr(mcp_service, "get_knowledge", AsyncMock(return_value={
        "id": "wk-1", "knowledge_base_id": "bound",
    }))
    issue_mock = AsyncMock()
    monkeypatch.setattr(mcp_service, "create_download_ticket", issue_mock)
    monkeypatch.setattr(mcp_service, "get_settings", lambda: SimpleNamespace(
        mcp_public_base_url="http://rag.example.com",
        frontend_origin="http://localhost:3002",
        app_env="production",
    ))

    try:
        asyncio.run(call_tool(
            session=None, user_id="u1", tool_name="rag_download_file",
            arguments={"document_id": "wk-1"},
            allowed_knowledge_base_ids={"bound"}, api_token_id=7,
        ))
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("生产环境应拒绝 HTTP 下载地址")
    issue_mock.assert_not_awaited()


def test_search_defaults_to_all_bound_libraries(monkeypatch):
    """省略范围时检索全部绑定库，合并结果并保留来源。"""
    async def search_library(**kwargs):
        """模拟各知识库的有序命中结果。"""
        kb_id = kwargs["kb_id"]
        return {"items": [{"id": f"{kb_id}-1"}, {"id": f"{kb_id}-2"}]}

    monkeypatch.setattr(mcp_service, "search_knowledge", search_library)
    monkeypatch.setattr(mcp_service, "get_kb_list", AsyncMock(return_value=[
        {"id": "a", "name": "文献库"}, {"id": "b", "name": "实验库"},
    ]))
    result = asyncio.run(call_tool(
        session=None, user_id="u1", tool_name="rag_search",
        arguments={"query": "实验", "top_k": 3},
        allowed_knowledge_base_ids={"b", "a"},
    ))
    assert result["kb_ids"] == ["a", "b"]
    assert [item["id"] for item in result["items"]] == ["a-1", "b-1", "a-2"]
    assert result["items"][0]["kb_name"] == "文献库"
    assert result["items"][1]["kb_id"] == "b"


def test_search_hit_exposes_weknora_document_id(monkeypatch):
    """检索命中可直接传给文档读取工具。"""
    monkeypatch.setattr(mcp_service, "search_knowledge", AsyncMock(return_value={
        "items": [{"knowledge_id": "wk-1", "content": "实验记录"}],
    }))
    monkeypatch.setattr(mcp_service, "get_kb_list", AsyncMock(return_value=[]))
    result = asyncio.run(call_tool(
        session=None, user_id="u1", tool_name="rag_search",
        arguments={"query": "实验", "kb_id": "bound"},
        allowed_knowledge_base_ids={"bound"},
    ))
    assert result["items"][0]["document_id"] == "wk-1"
    assert result["items"][0]["knowledge_id"] == "wk-1"


def test_search_result_excludes_internal_metadata_and_long_image_ocr(monkeypatch):
    """检索只返回智能体所需字段，避免原始元数据撑爆工具结果。"""
    monkeypatch.setattr(mcp_service, "search_knowledge", AsyncMock(return_value={
        "items": [{
            "id": "chunk-1",
            "knowledge_id": "wk-1",
            "knowledge_title": "实验论文",
            "content": "前置推理</think>显微图像显示桥接缺陷。" + "后文" * 1000,
            "matched_content": "重复内容" * 1000,
            "metadata": {"process_overrides": "冗长内部配置" * 1000},
            "image_info": '[{"url":"resource://abc123","caption":"桥接缺陷","ocr_text":"OCR"}]',
            "score": 0.25,
        }],
    }))
    monkeypatch.setattr(mcp_service, "get_kb_list", AsyncMock(return_value=[]))
    result = asyncio.run(call_tool(
        session=None, user_id="u1", tool_name="rag_search",
        arguments={"query": "桥接缺陷", "kb_id": "bound"},
        allowed_knowledge_base_ids={"bound"},
    ))
    hit = result["items"][0]
    assert hit["document_id"] == "wk-1"
    assert hit["knowledge_title"] == "实验论文"
    assert hit["image_info"] == [{"_resource_path": "resource://abc123", "caption": "桥接缺陷"}]
    assert hit["content"].startswith("显微图像显示桥接缺陷")
    assert len(hit["content"]) <= 1000
    assert "metadata" not in hit
    assert "matched_content" not in hit


def test_search_accepts_selected_libraries_and_removes_duplicates(monkeypatch):
    """kb_ids 仅检索指定绑定库且重复 ID 不重复调用。"""
    search_mock = AsyncMock(return_value={"items": []})
    monkeypatch.setattr(mcp_service, "search_knowledge", search_mock)
    monkeypatch.setattr(mcp_service, "get_kb_list", AsyncMock(return_value=[]))
    asyncio.run(call_tool(
        session=None, user_id="u1", tool_name="rag_search",
        arguments={"query": "实验", "kb_ids": ["b", "b"]},
        allowed_knowledge_base_ids={"a", "b"},
    ))
    search_mock.assert_awaited_once_with(kb_id="b", query="实验", top_k=5)


def test_search_rejects_invalid_scope_before_remote_calls(monkeypatch):
    """越权、歧义及非法参数不会触发任何上游检索。"""
    search_mock = AsyncMock()
    monkeypatch.setattr(mcp_service, "search_knowledge", search_mock)
    invalid_arguments = [
        {"kb_ids": ["a", "other"]},
        {"kb_id": "a", "kb_ids": ["a"]},
        {"kb_ids": []},
        {"kb_ids": "a"},
        {"kb_id": ""},
        {"top_k": 0},
        {"top_k": True},
        {"query": " "},
    ]
    for arguments in invalid_arguments:
        try:
            asyncio.run(call_tool(
                session=None, user_id="u1", tool_name="rag_search",
                arguments={"query": "实验", **arguments},
                allowed_knowledge_base_ids={"a"},
            ))
        except ValueError:
            pass
        else:
            raise AssertionError(f"应拒绝参数: {arguments}")
    search_mock.assert_not_awaited()


def test_search_reports_partial_failure(monkeypatch):
    """部分知识库失败时不能伪装成全库检索成功。"""
    from app.core.weknora import WeknoraError

    async def search_library(**kwargs):
        """模拟一个成功库和一个失败库。"""
        if kwargs["kb_id"] == "b":
            raise WeknoraError(503, "上游不可用")
        return {"items": [{"id": "hit"}]}

    monkeypatch.setattr(mcp_service, "search_knowledge", search_library)
    monkeypatch.setattr(mcp_service, "get_kb_list", AsyncMock(return_value=[]))
    result = asyncio.run(call_tool(
        session=None, user_id="u1", tool_name="rag_search",
        arguments={"query": "实验"}, allowed_knowledge_base_ids={"a", "b"},
    ))
    assert result["partial"] is True
    assert result["errors"][0]["kb_id"] == "b"
    assert result["items"][0]["kb_id"] == "a"
