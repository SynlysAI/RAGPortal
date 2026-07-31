"""FastAPI 应用入口。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.config import router as config_router
from app.api.v1.kb import router as kb_router
from app.api.v1.uploads import router as uploads_router
from app.core.config import get_settings
from app.core.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库。"""
    await init_db()
    yield


def create_app() -> FastAPI:
    """构建 FastAPI 实例并挂载路由。"""
    settings = get_settings()
    app = FastAPI(title="RAGPortal", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(config_router)
    app.include_router(kb_router)
    app.include_router(uploads_router)
    app.include_router(admin_router)
    return app


app = create_app()


@app.get("/api/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}


# 仅生产环境挂载前端静态文件(开发环境由 Vite dev server 提供)。
# 否则 StaticFiles(html=True) 会拦截非 GET 请求导致 405。
_settings = get_settings()
if _settings.app_env == "production":
    _frontend_dist = os.environ.get("FRONTEND_DIST", "../frontend/dist")
    if os.path.isdir(_frontend_dist):
        app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
