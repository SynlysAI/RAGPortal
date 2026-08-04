"""我的上传记录列表会先触发状态同步。"""
from fastapi.testclient import TestClient

from app.api.v1.auth import UserInfo, get_current_user
from app.api.v1 import uploads as uploads_api
from app.core.db import get_session
from app.main import app


class _FakeScalarResult:
    """模拟 SQLAlchemy scalars() 返回值。"""

    def __init__(self, items):
        self._items = items

    def all(self):
        """返回查询结果列表。"""
        return self._items


class _FakeResult:
    """模拟 SQLAlchemy execute() 的返回值。"""

    def __init__(self, items):
        self._items = items

    def scalars(self):
        """返回模拟的标量结果集。"""
        return _FakeScalarResult(self._items)


class _FakeSession:
    """模拟数据库会话。"""

    def __init__(self, items):
        self._items = items

    async def execute(self, stmt):
        """返回固定查询结果。"""
        return _FakeResult(self._items)


def test_my_uploads_list_triggers_status_sync(monkeypatch):
    """访问我的记录列表时应先刷新 pending/processing 状态。"""
    upload = uploads_api.Upload(
        id=1,
        knowledge_id="k-1",
        kb_id="kb-1",
        kb_name="测试知识库",
        uploader_user_id="u1",
        uploader_username="alice",
        uploader_organization="R&D",
        file_name="report.pdf",
        file_type="pdf",
        file_size=123,
        file_hash="",
        parse_status="pending",
        parse_error="",
        weknora_task_id="",
        uploaded_at="2026-08-03T00:00:00+08:00",
        last_synced_at="2026-08-03T00:00:00+08:00",
    )

    async def fake_sync_pending(session, limit=50):
        """模拟状态同步把记录推进到成功。"""
        upload.parse_status = "success"
        return 1

    async def fake_session_dep():
        """提供假的数据库会话。"""
        yield _FakeSession([upload])

    monkeypatch.setattr(uploads_api, "sync_pending", fake_sync_pending)
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        user_id="u1",
        username="alice",
        role="user",
        status="active",
        organization="R&D",
    )
    app.dependency_overrides[get_session] = fake_session_dep

    try:
        with TestClient(app) as client:
            resp = client.get("/api/uploads/mine")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["parse_status"] == "success"
    finally:
        app.dependency_overrides.clear()
