"""知识库列表服务:TTL 内存缓存。"""
import time
from typing import Any

from app.core.config import get_settings
from app.core.weknora import list_knowledge_bases

_cache: dict[str, Any] = {"data": [], "expires_at": 0.0}


async def get_kb_list(refresh: bool = False) -> list[dict[str, Any]]:
    """获取 KB 列表(命中缓存则直接返回)。

    Args:
        refresh: 是否强制刷新。

    Returns:
        KB 字典列表。
    """
    ttl = get_settings().kb_list_cache_ttl
    now = time.time()
    if not refresh and _cache["expires_at"] > now:
        return _cache["data"]
    data = await list_knowledge_bases()
    _cache["data"] = data
    _cache["expires_at"] = now + ttl
    return data


async def is_kb_allowed(kb_id: str) -> bool:
    """检查 kb_id 是否在 API Key 允许范围内。

    若缓存未命中,会自动刷新一次再判断。
    """
    kbs = await get_kb_list()
    if any(kb["id"] == kb_id for kb in kbs):
        return True
    kbs = await get_kb_list(refresh=True)
    return any(kb["id"] == kb_id for kb in kbs)


async def find_kb(kb_id: str) -> dict[str, Any] | None:
    """从缓存中查找 KB,返回 {id, name, type}。"""
    kbs = await get_kb_list()
    for kb in kbs:
        if kb["id"] == kb_id:
            return kb
    kbs = await get_kb_list(refresh=True)
    for kb in kbs:
        if kb["id"] == kb_id:
            return kb
    return None


def clear_cache() -> None:
    """清缓存(测试用)。"""
    _cache["data"] = []
    _cache["expires_at"] = 0.0
