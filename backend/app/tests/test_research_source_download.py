"""Plane 研究链原文件代理的授权测试。"""

from datetime import datetime, timezone
import hashlib
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.auth import UserInfo
from app.api.v1.integrations import download_research_file
from app.models.upload import Base, Upload


CONTENT = b"pdf!"
CONTENT_SHA256 = hashlib.sha256(CONTENT).hexdigest()
CONTENT_MD5 = hashlib.md5(CONTENT).hexdigest()


def _user(user_id="plane-research-bff"):
    """构造服务间下载接口的调用身份。"""
    return UserInfo(user_id=user_id, username=user_id, role="user")


def _upload(*, chain_id="chain-1", file_hash=CONTENT_MD5, file_size=len(CONTENT)):
    """构造一条带研究链作用域的上传记录。"""
    now = datetime.now(timezone.utc).isoformat()
    return Upload(
        knowledge_id="wk-1",
        kb_id="kb-1",
        kb_name="器件",
        uploader_user_id="plane-research-bff",
        uploader_username="plane-research-bff",
        workspace_slug="lab",
        research_project_id="project-1",
        chain_node_id="node-1",
        org_unit_id="org-1",
        org_unit_name="器件",
        chain_id=chain_id,
        file_name="论文.pdf",
        file_type="pdf",
        file_size=file_size,
        file_hash=file_hash,
        parse_status="success",
        uploaded_at=now,
        last_synced_at=now,
    )


@pytest.fixture
async def session():
    """提供仅包含上传表的临时数据库会话。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_plane_service_can_download_matched_research_file(session, monkeypatch):
    """Plane BFF 可用 SHA-256 读取保存 MD5 的历史记录。"""
    async with session() as database:
        database.add(_upload())
        await database.commit()
        monkeypatch.setattr(
            "app.api.v1.integrations.get_knowledge",
            AsyncMock(return_value={"id": "wk-1", "knowledge_base_id": "kb-1", "file_name": "论文.pdf"}),
        )
        monkeypatch.setattr(
            "app.api.v1.integrations.download_knowledge_file",
            AsyncMock(return_value=(CONTENT, "application/pdf")),
        )

        response = await download_research_file(
            "wk-1",
            chain_id="chain-1",
            node_id="node-1",
            kb_id="kb-1",
            file_hash=CONTENT_SHA256,
            user=_user(),
            session=database,
        )

    assert response.body == CONTENT
    assert response.media_type == "application/pdf"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_normal_user_cannot_use_service_download(session, monkeypatch):
    """普通登录身份不能冒用 Plane 服务间接口。"""
    download_mock = AsyncMock()
    monkeypatch.setattr("app.api.v1.integrations.download_knowledge_file", download_mock)

    async with session() as database:
        with pytest.raises(HTTPException) as exc:
            await download_research_file(
                "wk-1",
                chain_id="chain-1",
                node_id="node-1",
                kb_id="kb-1",
                file_hash=CONTENT_SHA256,
                user=_user("student-1"),
                session=database,
            )

    assert exc.value.status_code == 403
    download_mock.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chain_id", "node_id", "kb_id"),
    [
        ("other-chain", "node-1", "kb-1"),
        ("chain-1", "other-node", "kb-1"),
        ("chain-1", "node-1", "other-kb"),
    ],
)
async def test_scope_mismatch_is_hidden_as_not_found(session, monkeypatch, chain_id, node_id, kb_id):
    """任一研究作用域不匹配时不泄露记录存在性。"""
    download_mock = AsyncMock()
    monkeypatch.setattr("app.api.v1.integrations.download_knowledge_file", download_mock)

    async with session() as database:
        database.add(_upload())
        await database.commit()
        with pytest.raises(HTTPException) as exc:
            await download_research_file(
                "wk-1",
                chain_id=chain_id,
                node_id=node_id,
                kb_id=kb_id,
                file_hash=CONTENT_SHA256,
                user=_user(),
                session=database,
            )

    assert exc.value.status_code == 404
    download_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_plane_sha256_is_rejected_after_download(session, monkeypatch):
    """Plane 传入错误 SHA-256 时不能读取内容。"""
    async with session() as database:
        database.add(_upload())
        await database.commit()
        monkeypatch.setattr(
            "app.api.v1.integrations.get_knowledge",
            AsyncMock(return_value={"id": "wk-1", "knowledge_base_id": "kb-1"}),
        )
        monkeypatch.setattr(
            "app.api.v1.integrations.download_knowledge_file",
            AsyncMock(return_value=(CONTENT, "application/pdf")),
        )

        with pytest.raises(HTTPException) as exc:
            await download_research_file(
                "wk-1",
                chain_id="chain-1",
                node_id="node-1",
                kb_id="kb-1",
                file_hash="b" * 64,
                user=_user(),
                session=database,
            )

    assert exc.value.status_code == 502


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("download_content", "file_size", "stored_hash"),
    [
        pytest.param(b"<htm", len(CONTENT), CONTENT_MD5, id="html-instead-of-source"),
        pytest.param(CONTENT, len(CONTENT) + 1, CONTENT_MD5, id="size-mismatch"),
        pytest.param(CONTENT, len(CONTENT), "0" * 32, id="stored-md5-mismatch"),
    ],
)
async def test_changed_or_invalid_source_is_rejected(
    session, monkeypatch, download_content, file_size, stored_hash
):
    """尺寸、SHA-256 或历史 MD5 不匹配时不能把上游内容返回给 Plane。"""
    async with session() as database:
        database.add(_upload(file_hash=stored_hash, file_size=file_size))
        await database.commit()
        monkeypatch.setattr(
            "app.api.v1.integrations.get_knowledge",
            AsyncMock(return_value={"id": "wk-1", "knowledge_base_id": "kb-1"}),
        )
        monkeypatch.setattr(
            "app.api.v1.integrations.download_knowledge_file",
            AsyncMock(return_value=(download_content, "text/html")),
        )

        with pytest.raises(HTTPException) as exc:
            await download_research_file(
                "wk-1",
                chain_id="chain-1",
                node_id="node-1",
                kb_id="kb-1",
                file_hash=CONTENT_SHA256,
                user=_user(),
                session=database,
            )

    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_legacy_upload_without_chain_id_still_matches_node(session, monkeypatch):
    """历史记录缺少 chain_id 时以 chain_node_id 作为链路匹配权威。"""
    async with session() as database:
        database.add(_upload(chain_id=""))
        await database.commit()
        monkeypatch.setattr(
            "app.api.v1.integrations.get_knowledge",
            AsyncMock(return_value={"id": "wk-1", "knowledge_base_id": "kb-1"}),
        )
        monkeypatch.setattr(
            "app.api.v1.integrations.download_knowledge_file",
            AsyncMock(return_value=(CONTENT, "application/pdf")),
        )

        response = await download_research_file(
            "wk-1",
            chain_id="chain-1",
            node_id="node-1",
            kb_id="kb-1",
            file_hash=CONTENT_SHA256,
            user=_user(),
            session=database,
        )

    assert response.body == CONTENT


@pytest.mark.asyncio
async def test_document_moved_to_another_knowledge_base_is_hidden(session, monkeypatch):
    """上传记录匹配但 WeKnora 文档移库后仍拒绝下载。"""
    async with session() as database:
        database.add(_upload())
        await database.commit()
        monkeypatch.setattr(
            "app.api.v1.integrations.get_knowledge",
            AsyncMock(return_value={"id": "wk-1", "knowledge_base_id": "other-kb"}),
        )
        download_mock = AsyncMock()
        monkeypatch.setattr("app.api.v1.integrations.download_knowledge_file", download_mock)

        with pytest.raises(HTTPException) as exc:
            await download_research_file(
                "wk-1",
                chain_id="chain-1",
                node_id="node-1",
                kb_id="kb-1",
                file_hash=CONTENT_SHA256,
                user=_user(),
                session=database,
            )

    assert exc.value.status_code == 404
    download_mock.assert_not_awaited()
