"""认证相关路由:登录代理 / 当前用户 / 退出。"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
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
async def login(body: LoginRequest) -> JSONResponse:
    """代理 AI4MS 登录接口。

    通过 RAGPortal 后端转发,避免前端跨域 + 不暴露 AI4MS 后端地址。
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{settings.ai4ms_base_url}/auth/login",
            json={"username": body.username, "password": body.password},
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=resp.json().get("detail", "登录失败"),
        )
    data = resp.json()
    return JSONResponse(content=data)


@router.get("/me")
async def me(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """返回当前用户信息。"""
    return user


@router.post("/logout")
async def logout() -> dict:
    """退出(无服务端态,前端清 token 即可)。"""
    return {"ok": True}
