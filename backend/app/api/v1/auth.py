"""认证相关路由:登录代理 / 当前用户 / 退出。"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.auth import parse_token
from app.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """登录请求体。"""

    username: str
    password: str


class UserInfo(BaseModel):
    """对前端暴露的用户信息。"""

    user_id: str
    username: str
    role: str
    status: str = "active"
    organization: str = ""


def _normalize_user_info(payload: dict) -> UserInfo:
    """将上游用户信息规范化为 RAGPortal 的用户模型。

    Args:
        payload: AI4MS 返回的用户信息字典。

    Returns:
        RAGPortal 内部统一使用的用户信息对象。
    """
    return UserInfo(
        user_id=str(payload.get("user_id", "")),
        username=str(payload.get("username", "")),
        role=str(payload.get("role", "")),
        status=str(payload.get("status", "active")),
        organization=str(payload.get("organization", "")),
    )


def _normalize_login_response(payload: dict) -> dict:
    """将 AI4MS 登录响应规范化为前端可直接消费的结构。

    Args:
        payload: AI4MS 登录接口响应体。

    Returns:
        包含 token 和 user 的登录结果字典。
    """
    data = payload.get("data")
    if isinstance(data, dict):
        payload = data
    user = payload.get("user") or {}
    if not isinstance(user, dict):
        user = {}
    normalized_user = _normalize_user_info(user)
    token = str(payload.get("token", "")).strip()
    if not token:
        raise HTTPException(status_code=502, detail="AI4MS 登录响应缺少 token")
    return {"token": token, "user": normalized_user.model_dump()}


async def get_current_user(request: Request) -> UserInfo:
    """FastAPI 依赖:从 Authorization header 解析当前用户。

    Raises:
        HTTPException: 401 未提供 token / token 无效。
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    token = auth[7:]
    payload = parse_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return UserInfo(
        user_id=payload["sub"],
        username=payload["username"],
        role=payload["role"],
        status="active",
        organization=payload.get("organization", ""),
    )


async def get_current_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """FastAPI 依赖:仅允许 admin。"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@router.post("/login")
async def login(body: LoginRequest) -> dict:
    """代理 AI4MS 登录接口。

    通过 RAGPortal 后端转发,避免前端跨域 + 不暴露 AI4MS 后端地址。
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.resolved_ai4ms_api_base_url}/auth/login",
                json={"username": body.username, "password": body.password},
            )
        if resp.status_code != 200:
            detail = "登录失败"
            try:
                detail = resp.json().get("detail", detail)
            except Exception:
                pass
            raise HTTPException(status_code=resp.status_code, detail=detail)
        response_data = resp.json()
        if not isinstance(response_data, dict):
            raise HTTPException(status_code=502, detail="AI4MS 登录响应格式错误")
        return _normalize_login_response(response_data)
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="无法连接到 AI4MS 认证服务")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI4MS 认证服务响应超时")


@router.get("/me")
async def me(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """返回当前用户信息。"""
    return user


@router.post("/logout")
async def logout() -> dict:
    """退出(无服务端态,前端清 token 即可)。"""
    return {"ok": True}
