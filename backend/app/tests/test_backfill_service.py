"""WeKnora 历史回写服务测试。"""
import pytest

from app.models.upload import Upload
from app.services.backfill_service import (
    DELETED_ERROR,
    DELETED_STATUS,
    SYSTEM_USER_ID,
    SYSTEM_USERNAME,
    UNKNOWN_SOURCE,
    _extract_uploader,
    _mark_missing_knowledge_deleted,
    _parse_metadata,
    _upsert_knowledge,
)


class _FakeScalarResult:
    """模拟 SQLAlchemy scalars() 返回值。"""

    def __init__(self, items):
        self._items = items

    def all(self):
        """返回模拟记录列表。"""
        return self._items

    def first(self):
        """返回首条模拟记录。"""
        return self._items[0] if self._items else None


class _FakeResult:
    """模拟 SQLAlchemy execute() 返回值。"""

    def __init__(self, items):
        self._items = items

    def scalars(self):
        """返回模拟标量结果。"""
        return _FakeScalarResult(self._items)


class _FakeSession:
    """模拟数据库会话。"""

    def __init__(self, items):
        self._items = items
        self.commits = 0
        self.added = []

    async def execute(self, stmt):
        """返回固定查询记录。"""
        return _FakeResult(self._items)

    def add(self, item):
        """记录新增对象。"""
        self.added.append(item)

    async def commit(self):
        """记录提交次数。"""
        self.commits += 1


def test_extract_uploader_from_metadata():
    """metadata 中存在上传者信息时应保留真实上传者。"""
    uploader = _extract_uploader({
        "uploader_id": "u1",
        "uploader_name": "alice",
        "uploader_org": "R&D",
    })

    assert uploader["uploader_user_id"] == "u1"
    assert uploader["uploader_username"] == "alice"
    assert uploader["uploader_organization"] == "R&D"


def test_extract_uploader_falls_back_to_system_upload():
    """metadata 缺失上传者时回退为系统上传。"""
    uploader = _extract_uploader({})

    assert uploader["uploader_user_id"] == SYSTEM_USER_ID
    assert uploader["uploader_username"] == SYSTEM_USERNAME
    assert uploader["uploader_organization"] == UNKNOWN_SOURCE


def test_parse_metadata_accepts_json_string():
    """metadata 为 JSON 字符串时应正常解析。"""
    metadata = _parse_metadata('{"uploader_name":"alice"}')

    assert metadata["uploader_name"] == "alice"


@pytest.mark.asyncio
async def test_mark_missing_knowledge_deleted():
    """本地存在但 WeKnora 当前列表缺失的记录应标记为上游已删除。"""
    missing = Upload(
        id=1,
        knowledge_id="missing",
        kb_id="kb-1",
        kb_name="测试知识库",
        uploader_user_id="u1",
        uploader_username="alice",
        uploader_organization="R&D",
        file_name="missing.pdf",
        file_type="pdf",
        file_size=123,
        file_hash="",
        parse_status="success",
        parse_error="",
        weknora_task_id="",
        uploaded_at="2026-08-03T00:00:00+08:00",
        last_synced_at="2026-08-03T00:00:00+08:00",
    )
    existing = Upload(
        id=2,
        knowledge_id="existing",
        kb_id="kb-1",
        kb_name="测试知识库",
        uploader_user_id="u1",
        uploader_username="alice",
        uploader_organization="R&D",
        file_name="existing.pdf",
        file_type="pdf",
        file_size=123,
        file_hash="",
        parse_status="success",
        parse_error="",
        weknora_task_id="",
        uploaded_at="2026-08-03T00:00:00+08:00",
        last_synced_at="2026-08-03T00:00:00+08:00",
    )
    session = _FakeSession([missing, existing])

    deleted = await _mark_missing_knowledge_deleted(session, "kb-1", {"existing"})

    assert deleted == 1
    assert missing.parse_status == DELETED_STATUS
    assert missing.parse_error == DELETED_ERROR
    assert existing.parse_status == "success"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_upsert_knowledge_persists_file_hash():
    """历史回写时应把 WeKnora 返回的 file_hash 一并保存。"""
    session = _FakeSession([])
    kb = {"id": "kb-1", "name": "测试知识库"}
    knowledge = {
        "id": "k-1",
        "file_name": "report.pdf",
        "file_type": "pdf",
        "file_size": 123,
        "file_hash": "abc123",
        "metadata": {"uploader_name": "alice"},
        "parse_status": "success",
        "created_at": "2026-08-03T00:00:00+08:00",
    }

    result = await _upsert_knowledge(session, kb, knowledge)

    assert result == "created"
    assert session.added[0].file_hash == "abc123"
