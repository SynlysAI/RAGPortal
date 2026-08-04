"""数据库连接与初始化。"""
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import kb_request as _kb_request_model  # noqa: F401
from app.models.upload import Base


def _build_url() -> str:
    """根据配置生成 SQLAlchemy aiosqlite 连接串。

    Returns:
        形如 sqlite+aiosqlite:///E:/github_project/RAGPortal/backend/data/ragportal.db 的 URL。
    """
    path = Path(get_settings().sqlite_path)
    if not path.is_absolute():
        # 相对路径相对于 backend/ 目录解析(此文件位于 backend/app/core/)
        path = Path(__file__).resolve().parent.parent.parent / path
    path.parent.mkdir(parents=True, exist_ok=True)
    # Windows 路径转 posix,sqlite 多 / OK
    return f"sqlite+aiosqlite:///{path.as_posix()}"


engine = create_async_engine(_build_url(), echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _migrate_uploads_table(sync_conn) -> None:
    """补齐 uploads 表的历史列与索引。

    Args:
        sync_conn: SQLAlchemy 同步连接。
    """
    inspector = inspect(sync_conn)
    try:
        columns = {column["name"] for column in inspector.get_columns("uploads")}
    except Exception:
        columns = set()
    if "file_hash" not in columns:
        sync_conn.execute(
            text(
                "ALTER TABLE uploads ADD COLUMN file_hash VARCHAR(64) NOT NULL DEFAULT ''"
            )
        )
    sync_conn.execute(text("CREATE INDEX IF NOT EXISTS idx_uploads_kb_hash ON uploads (kb_id, file_hash)"))


async def init_db() -> None:
    """启动时建表。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_uploads_table)


async def get_session() -> AsyncSession:
    """FastAPI 依赖:提供数据库会话。"""
    async with async_session() as session:
        yield session
