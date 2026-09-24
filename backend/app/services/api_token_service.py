"""账户级 API Token 生成、验证和管理服务。"""

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_token import ApiToken

ALL_PERMISSIONS = {
    "documents:list",
    "documents:search",
    "documents:read",
    "documents:download",
    "documents:write",
    "documents:update",
}
READ_PERMISSIONS = {
    "documents:list",
    "documents:search",
    "documents:read",
    "documents:download",
}


@dataclass(frozen=True)
class CreatedApiToken:
    """创建 Token 的结果，secret 只在此结果中返回一次。"""

    token: ApiToken
    secret: str


def _now() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def hash_token(secret: str) -> str:
    """计算 Token 摘要。

    Args:
        secret: Token 明文。

    Returns:
        SHA-256 十六进制摘要。
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _normalize_permissions(permissions: set[str] | list[str]) -> set[str]:
    """过滤并规范化 Token 权限。"""
    return {permission.strip() for permission in permissions if permission.strip()} & ALL_PERMISSIONS


async def create_api_token(
    *,
    session: AsyncSession,
    user_id: str,
    username: str,
    name: str,
    permissions: set[str] | list[str],
    expires_at: str = "",
) -> CreatedApiToken:
    """创建账户级 API Token。

    Args:
        session: 数据库会话。
        user_id: Token 所属 AI4MS 用户 ID。
        username: 用户名快照。
        name: Token 显示名称。
        permissions: 允许调用的 Tool 权限集合。
        expires_at: 可选的 ISO 8601 过期时间。

    Returns:
        包含一次性明文 secret 和数据库对象的结果。
    """
    normalized = _normalize_permissions(permissions)
    secret = f"rpt_{secrets.token_urlsafe(32)}"
    token = ApiToken(
        user_id=user_id,
        username=username,
        name=name.strip() or "未命名 Token",
        token_prefix=secret[:12],
        token_hash=hash_token(secret),
        permissions_json=json.dumps(sorted(normalized), ensure_ascii=False),
        created_at=_now(),
        expires_at=expires_at.strip(),
    )
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return CreatedApiToken(token=token, secret=secret)


async def verify_api_token(
    session: AsyncSession,
    secret: str,
    permission: str | None = None,
) -> ApiToken | None:
    """验证 Token 状态、有效期和可选权限。

    Args:
        session: 数据库会话。
        secret: Bearer Token 明文。
        permission: 要求的权限；为空时只验证 Token 本身。

    Returns:
        有效的 ApiToken；无效或无权限时返回 None。
    """
    if not secret:
        return None
    result = await session.execute(
        select(ApiToken).where(ApiToken.token_hash == hash_token(secret))
    )
    token = result.scalar_one_or_none()
    if token is None or token.status != "active":
        return None
    now = datetime.now(timezone.utc)
    if token.expires_at:
        try:
            expires = datetime.fromisoformat(token.expires_at)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= now:
                return None
        except ValueError:
            return None
    permissions = set(json.loads(token.permissions_json or "[]"))
    if permission and permission not in permissions:
        return None
    token.last_used_at = now.isoformat()
    await session.commit()
    return token


async def revoke_api_token(session: AsyncSession, token_id: int, user_id: str) -> bool:
    """撤销指定用户的 Token。"""
    result = await session.execute(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user_id)
    )
    token = result.scalar_one_or_none()
    if token is None:
        return False
    token.status = "revoked"
    token.revoked_at = _now()
    await session.commit()
    return True
