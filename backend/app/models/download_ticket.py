"""短期文件下载凭证 ORM 模型。"""

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.upload import Base


class DownloadTicket(Base):
    """绑定单个 WeKnora 文档和签发 Token 的短期下载凭证。"""

    __tablename__ = "download_tickets"

    ticket_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_token_id: Mapped[int] = mapped_column(Integer, nullable=False)
    knowledge_id: Mapped[str] = mapped_column(String(128), nullable=False)
    kb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ticket_type: Mapped[str] = mapped_column(String(16), nullable=False, default="document")
    resource_path: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        Index("idx_download_tickets_expiry", "expires_at"),
        Index("idx_download_tickets_api_token", "api_token_id"),
    )
