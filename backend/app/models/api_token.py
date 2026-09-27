"""账户级 API Token ORM 模型。"""

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.upload import Base


class ApiToken(Base):
    """绑定到 AI4MS 用户的 RAGPortal API Token。"""

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    permissions_json: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_base_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    last_used_at: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    revoked_at: Mapped[str] = mapped_column(String(32), default="", nullable=False)

    __table_args__ = (
        Index("idx_api_tokens_user_status", "user_id", "status"),
        Index("idx_api_tokens_hash", "token_hash"),
    )
