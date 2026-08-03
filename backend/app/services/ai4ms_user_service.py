"""AI4MS 用户信息代理服务。"""
from typing import Any

import httpx
from fastapi import HTTPException

from app.api.v1.auth import UserInfo
from app.core.config import get_settings


def _normalize_user(payload: dict[str, Any]) -> UserInfo:
    """将 AI4MS 用户对象规范化为 RAGPortal 用户对象。

    Args:
        payload: AI4MS 返回的用户对象。

    Returns:
        RAGPortal 内部统一使用的用户信息对象。
    """
    return UserInfo(
        user_id=str(payload.get("user_id") or "").strip(),
        username=str(payload.get("username") or "").strip(),
        role=str(payload.get("role") or "user").strip(),
        status=str(payload.get("status") or "active").strip(),
        organization=str(payload.get("organization") or "").strip(),
    )


def _extract_users(payload: dict[str, Any]) -> list[UserInfo]:
    """从 AI4MS 标准响应中提取用户列表。

    Args:
        payload: AI4MS 用户列表接口响应。

    Returns:
        用户信息列表。
    """
    raw_items = payload.get("data") or payload.get("items") or payload
    if not isinstance(raw_items, list):
        return []
    users = [_normalize_user(item) for item in raw_items if isinstance(item, dict)]
    return [user for user in users if user.user_id and user.username]


async def list_ai4ms_users(authorization: str) -> list[UserInfo]:
    """从 AI4MS 获取用户列表。

    Args:
        authorization: 当前管理员的 Authorization 头。

    Returns:
        AI4MS 用户列表。

    Raises:
        HTTPException: AI4MS 用户接口不可用或鉴权失败。
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.resolved_ai4ms_api_base_url}/admin/users",
                headers={"Authorization": authorization},
            )
    except httpx.ConnectError as exc:
        raise HTTPException(status_code=502, detail="无法连接到 AI4MS 用户服务") from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="AI4MS 用户服务响应超时") from exc

    if resp.status_code != 200:
        detail = "拉取 AI4MS 用户列表失败"
        try:
            data = resp.json()
            detail = data.get("detail") or data.get("message") or detail
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)
    data = resp.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="AI4MS 用户列表响应格式错误")
    return list_ai4ms_users_from_payload(data)


def list_ai4ms_users_from_payload(payload: dict[str, Any]) -> list[UserInfo]:
    """从响应体解析 AI4MS 用户列表。

    Args:
        payload: AI4MS 用户列表接口响应。

    Returns:
        用户信息列表。
    """
    return _extract_users(payload)


async def find_ai4ms_user(authorization: str, user_id: str) -> UserInfo | None:
    """按 user_id 从 AI4MS 用户列表中查找用户。

    Args:
        authorization: 当前管理员的 Authorization 头。
        user_id: 目标用户 ID。

    Returns:
        找到时返回用户信息；否则返回 None。
    """
    target_user_id = user_id.strip()
    if not target_user_id:
        return None
    users = await list_ai4ms_users(authorization)
    for user in users:
        if user.user_id == target_user_id:
            return user
    return None
