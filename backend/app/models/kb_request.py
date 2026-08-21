"""知识库申请 ORM 模型。"""
from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.upload import Base


class KbRequest(Base):
    """普通用户提交的知识库申请。"""

    __tablename__ = "kb_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requester_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requester_username: Mapped[str] = mapped_column(String(128), nullable=False)
    requester_organization: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    requested_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    request_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 是否创建 wiki 知识库(需要提取重点)
    want_wiki: Mapped[bool] = mapped_column(default=False, nullable=False)
    # 是否创建 LLM 知识图谱(需要提取重点 + 关系类型标签 + 示例文本)
    want_llm_graph: Mapped[bool] = mapped_column(default=False, nullable=False)
    # 提取重点:应重点识别的实体和概念
    extract_focus: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 关系类型标签:逗号分隔
    relation_types: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 示例文档文本
    example_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    reviewer_user_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    reviewer_username: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    review_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    approved_kb_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    approved_kb_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    create_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        Index("idx_kb_requests_status", "status"),
        Index("idx_kb_requests_requester", "requester_user_id", "created_at"),
        Index("idx_kb_requests_created_at", "created_at"),
    )
