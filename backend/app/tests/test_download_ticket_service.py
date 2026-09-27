"""短期下载凭证服务测试。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.api_token import ApiToken
from app.models.download_ticket import DownloadTicket
from app.models.upload import Base
from app.services.download_ticket_service import (
    create_image_ticket,
    create_download_ticket,
    resolve_download_ticket,
)


@pytest.fixture
async def ticket_session():
    """提供隔离的内存数据库会话。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        token = ApiToken(
            user_id="u1",
            username="alice",
            name="下载测试",
            token_prefix="rpt_test",
            token_hash="a" * 64,
            permissions_json='["documents:download", "documents:search"]',
            knowledge_base_ids_json='["kb-a"]',
            status="active",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)
        yield session, token
    await engine.dispose()


@pytest.mark.asyncio
async def test_ticket_stores_only_hash_and_expires_in_ten_minutes(ticket_session):
    """下载凭证只存摘要，签发后有效十分钟。"""
    session, token = ticket_session
    before = datetime.now(timezone.utc)

    issued = await create_download_ticket(session, token.id, "wk-1", "kb-a")
    stored = (await session.execute(select(DownloadTicket))).scalar_one()

    assert issued.secret not in stored.ticket_hash
    assert len(stored.ticket_hash) == 64
    assert stored.knowledge_id == "wk-1"
    assert timedelta(minutes=9, seconds=59) < issued.expires_at - before
    assert issued.expires_at - before < timedelta(minutes=10, seconds=2)
    assert (await resolve_download_ticket(session, issued.secret)).knowledge_id == "wk-1"
    assert (await resolve_download_ticket(session, issued.secret)).knowledge_id == "wk-1"


@pytest.mark.asyncio
async def test_ticket_invalid_after_token_revocation(ticket_session):
    """撤销 API Token 后，其已签发下载链接立即失效。"""
    session, token = ticket_session
    issued = await create_download_ticket(session, token.id, "wk-1", "kb-a")

    token.status = "revoked"
    await session.commit()

    assert await resolve_download_ticket(session, issued.secret) is None


@pytest.mark.asyncio
async def test_ticket_invalid_after_expiration_or_scope_change(ticket_session):
    """过期或知识库授权变化后，下载链接失效。"""
    session, token = ticket_session
    issued = await create_download_ticket(session, token.id, "wk-1", "kb-a")
    token.knowledge_base_ids_json = '[]'
    await session.commit()
    assert await resolve_download_ticket(session, issued.secret) is None


@pytest.mark.asyncio
async def test_image_ticket_uses_configured_longer_ttl(ticket_session):
    """图片 Markdown 凭证支持 30 天有效期并保存资源引用。"""
    session, token = ticket_session
    issued = await create_image_ticket(
        session, token.id, "wk-1", "kb-a", "resource://image", 2_592_000,
    )
    stored = (await session.execute(select(DownloadTicket))).scalar_one()
    assert stored.ticket_type == "image"
    assert stored.resource_path == "resource://image"
    assert issued.expires_at - datetime.now(timezone.utc) > timedelta(days=29)
    assert (await resolve_download_ticket(session, issued.secret)).ticket_type == "image"

    token.knowledge_base_ids_json = '["kb-a"]'
    token.permissions_json = '[]'
    await session.commit()
    assert await resolve_download_ticket(session, issued.secret) is None

    token.permissions_json = '["documents:download"]'
    stored = (await session.execute(select(DownloadTicket))).scalar_one()
    stored.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    await session.commit()
    assert await resolve_download_ticket(session, issued.secret) is None
