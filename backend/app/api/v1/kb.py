"""知识库列表路由(代理 WeKnora,带缓存)。"""
from fastapi import APIRouter, Depends, Query

from app.api.v1.auth import get_current_user, UserInfo
from app.services.kb_service import get_kb_list

router = APIRouter(prefix="/api/kb", tags=["kb"])


@router.get("/list")
async def list_kbs(
    refresh: bool = Query(False),
    user: UserInfo = Depends(get_current_user),
) -> dict:
    """获取当前 API Key 能访问的所有 KB。"""
    items = await get_kb_list(refresh=refresh)
    return {"items": items}
