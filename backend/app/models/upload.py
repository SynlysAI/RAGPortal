"""上传记录 ORM 模型。"""
from sqlalchemy import Integer, String, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""


class Upload(Base):
    """文档上传记录。每条记录对应 WeKnora 中一个 knowledge 条目。"""

    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    kb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kb_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uploader_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    uploader_username: Mapped[str] = mapped_column(String(128), nullable=False)
    uploader_organization: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    parse_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    weknora_task_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    uploaded_at: Mapped[str] = mapped_column(String(32), nullable=False)
    last_synced_at: Mapped[str] = mapped_column(String(32), default="", nullable=False)

    __table_args__ = (
        Index("idx_uploads_user_time", "uploader_user_id", "uploaded_at"),
        Index("idx_uploads_kb_time", "kb_id", "uploaded_at"),
        Index("idx_uploads_status", "parse_status"),
        Index("idx_uploads_time", "uploaded_at"),
    )
