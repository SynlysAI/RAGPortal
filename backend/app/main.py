"""FastAPI 应用入口。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.v1.admin import router as admin_router
from app.api.v1.admin_kb_requests import router as admin_kb_requests_router
from app.api.v1.auth import router as auth_router
from app.api.v1.config import router as config_router
from app.api.v1.kb import router as kb_router
from app.api.v1.kb_requests import router as kb_requests_router
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
    app.include_router(kb_requests_router)
    app.include_router(uploads_router)
    app.include_router(admin_router)
    app.include_router(admin_kb_requests_router)
    return app


app = create_app()


@app.get("/api/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}


# 只要前端构建产物存在,就允许后端直接托管静态文件。
# 开发期如果不需要静态托管,保持 frontend/dist 不存在即可。
_frontend_dist = os.environ.get("FRONTEND_DIST", "../frontend/dist")
if os.path.isdir(_frontend_dist):

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """托管前端 SPA，并回退到 index.html。

        Args:
            full_path: 请求路径。

        Returns:
            静态资源文件或前端入口页。
        """
        file_path = os.path.join(_frontend_dist, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_frontend_dist, "index.html"))
