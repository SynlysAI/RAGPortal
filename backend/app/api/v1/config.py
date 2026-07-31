"""前端公共配置接口(无需登录)。"""
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def get_public_config() -> dict:
    """返回前端需要的非敏感配置。

    Returns:
        portal_url: AI4MS 门户地址(用于"前往注册"外链)。
        max_size_mb: 上传文件大小上限。
        allowed_file_types: 允许的文件扩展名列表。
    """
    s = get_settings()
    return {
        "portal_url": s.ai4ms_portal_url,
        "max_size_mb": s.upload_max_size_mb,
        "allowed_file_types": sorted(s.allowed_file_types_set),
    }
