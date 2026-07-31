"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.config import router as config_router
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
    return app


app = create_app()


@app.get("/api/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}
