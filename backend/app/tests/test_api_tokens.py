"""账户级 API Token 服务测试。"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.api_token import ApiToken
from app.models.upload import Base
from app.services.api_token_service import (
    ALL_PERMISSIONS,
    create_api_token,
    revoke_api_token,
    verify_api_token,
)


def test_create_token_returns_secret_once_and_verifies_permissions():
    """创建 Token 只返回一次明文，并按权限校验。"""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = await create_api_token(
                session=session,
                user_id="u1",
                username="alice",
                name="WorkBuddy",
                permissions={"documents:search", "documents:read"},
            )
            assert result.secret.startswith("rpt_")
            assert result.token.token_hash != result.secret
            assert result.token.permissions_json
            assert await verify_api_token(session, result.secret, "documents:search")
            assert not await verify_api_token(session, result.secret, "documents:write")
        await engine.dispose()

    asyncio.run(run())


def test_revoked_token_is_invalid():
    """撤销 Token 后立即不能再验证。"""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = await create_api_token(
                session=session,
                user_id="u1",
                username="alice",
                name="临时 Token",
                permissions=ALL_PERMISSIONS,
            )
            await revoke_api_token(session, result.token.id, "u1")
            assert await verify_api_token(session, result.secret) is None
        await engine.dispose()

    asyncio.run(run())
