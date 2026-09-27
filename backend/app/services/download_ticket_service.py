"""短期文件下载凭证签发与验证。"""

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_token import ApiToken
from app.models.download_ticket import DownloadTicket

DOWNLOAD_TICKET_TTL = timedelta(minutes=10)


@dataclass(frozen=True)
class IssuedDownloadTicket:
    """仅在签发时包含下载凭证明文的结果。"""

    secret: str
    expires_at: datetime


def _hash_ticket(secret: str) -> str:
    """计算下载凭证摘要。

    Args:
        secret: 下载凭证明文。

    Returns:
        SHA-256 十六进制摘要。
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _token_can_access(
    token: ApiToken | None,
    kb_id: str,
    now: datetime,
    permission: str,
) -> bool:
    """检查原 API Token 当前是否仍可访问指定知识库。

    Args:
        token: 签发下载凭证的 API Token。
        kb_id: 文档所属知识库 ID。
        now: 当前 UTC 时间。

        permission: 所需 Token 权限。

    Returns:
        Token 状态、有效期、权限和知识库范围均有效时返回 True。
    """
    if token is None or token.status != "active":
        return False
    try:
        if permission not in json.loads(token.permissions_json or "[]"):
            return False
        if kb_id not in json.loads(token.knowledge_base_ids_json or "[]"):
            return False
        if token.expires_at:
            expires_at = datetime.fromisoformat(token.expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                return False
    except (ValueError, TypeError):
        return False
    return True


async def create_download_ticket(
    session: AsyncSession,
    api_token_id: int,
    knowledge_id: str,
    kb_id: str,
) -> IssuedDownloadTicket:
    """为一个已授权文档签发十分钟下载凭证。

    Args:
        session: 数据库会话。
        api_token_id: 原 API Token ID。
        knowledge_id: WeKnora 文档 ID。
        kb_id: 文档所属知识库 ID。

    Returns:
        一次性返回的凭证明文和过期时间。

    Raises:
        ValueError: 原 Token 已失效或无下载权限。
    """
    now = datetime.now(timezone.utc)
    token = await session.get(ApiToken, api_token_id)
    if not _token_can_access(token, kb_id, now, "documents:download"):
        raise ValueError("Token 无权下载此文档")
    secret = f"rdl_{secrets.token_urlsafe(32)}"
    expires_at = now + DOWNLOAD_TICKET_TTL
    await session.execute(delete(DownloadTicket).where(
        DownloadTicket.expires_at <= now.isoformat(),
    ))
    session.add(DownloadTicket(
        ticket_hash=_hash_ticket(secret),
        api_token_id=api_token_id,
        knowledge_id=knowledge_id,
        kb_id=kb_id,
        ticket_type="document",
        resource_path="",
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
    ))
    await session.commit()
    return IssuedDownloadTicket(secret=secret, expires_at=expires_at)


async def create_image_ticket(
    session: AsyncSession,
    api_token_id: int,
    knowledge_id: str,
    kb_id: str,
    resource_path: str,
    ttl_seconds: int,
) -> IssuedDownloadTicket:
    """为检索图片签发可放入 Markdown 的长期短期凭证。

    Args:
        session: 数据库会话。
        api_token_id: 原 API Token ID。
        knowledge_id: 图片所属 WeKnora 文档 ID。
        kb_id: 图片所属知识库 ID。
        resource_path: WeKnora resource:// 图片引用。
        ttl_seconds: 凭证有效秒数。

    Returns:
        图片 URL 所需的凭证明文和过期时间。
    """
    if not resource_path.startswith("resource://"):
        raise ValueError("图片资源引用无效")
    now = datetime.now(timezone.utc)
    token = await session.get(ApiToken, api_token_id)
    if not _token_can_access(token, kb_id, now, "documents:search"):
        raise ValueError("Token 无权读取此检索图片")
    if not 60 <= ttl_seconds <= 31_536_000:
        raise ValueError("图片链接有效期必须在 60 秒到 365 天之间")
    secret = f"rim_{secrets.token_urlsafe(32)}"
    expires_at = now + timedelta(seconds=ttl_seconds)
    await session.execute(delete(DownloadTicket).where(
        DownloadTicket.expires_at <= now.isoformat(),
    ))
    session.add(DownloadTicket(
        ticket_hash=_hash_ticket(secret),
        api_token_id=api_token_id,
        knowledge_id=knowledge_id,
        kb_id=kb_id,
        ticket_type="image",
        resource_path=resource_path,
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
    ))
    await session.commit()
    return IssuedDownloadTicket(secret=secret, expires_at=expires_at)


async def resolve_download_ticket(
    session: AsyncSession,
    secret: str,
) -> DownloadTicket | None:
    """验证下载凭证及原 API Token 的当前授权状态。

    Args:
        session: 数据库会话。
        secret: URL 中的短期下载凭证明文。

    Returns:
        凭证有效时返回记录；否则返回 None。
    """
    if not secret.startswith(("rdl_", "rim_")):
        return None
    ticket = await session.get(DownloadTicket, _hash_ticket(secret))
    if ticket is None:
        return None
    now = datetime.now(timezone.utc)
    try:
        if datetime.fromisoformat(ticket.expires_at) <= now:
            return None
    except ValueError:
        return None
    token = await session.get(ApiToken, ticket.api_token_id)
    permission = "documents:search" if ticket.ticket_type == "image" else "documents:download"
    if not _token_can_access(token, ticket.kb_id, now, permission):
        return None
    return ticket
