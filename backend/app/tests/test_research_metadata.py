"""Plane Research Chain 上传 metadata contract fixture。"""

from fastapi.testclient import TestClient

from app.api.v1.auth import UserInfo, get_current_user
from app.core.db import get_session
from app.main import app
from app.models.upload import Upload


def test_upload_accepts_complete_research_metadata(monkeypatch):
    """完整课题 metadata 会传入上传服务并随上传详情返回。"""
    captured = {}

    async def fake_handle_upload(**kwargs):
        """记录服务层收到的课题 metadata。"""
        captured.update(kwargs)
        return Upload(
            knowledge_id="knowledge-1",
            kb_id=kwargs["kb_id"],
            kb_name="Materials",
            uploader_user_id=kwargs["uploader_user_id"],
            uploader_username=kwargs["uploader_username"],
            uploader_organization=kwargs["uploader_organization"],
            workspace_slug=kwargs["workspace_slug"],
            research_project_id=kwargs["research_project_id"],
            chain_node_id=kwargs["chain_node_id"],
            file_name="paper.pdf",
            file_type="pdf",
            file_size=4,
            parse_status="pending",
        )

    async def fake_session_dep():
        """上传接口测试不需要真实数据库事务。"""
        yield None

    monkeypatch.setattr("app.api.v1.uploads.handle_upload", fake_handle_upload)
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        user_id="user-1", username="alice", role="user", status="active", organization="R&D"
    )
    app.dependency_overrides[get_session] = fake_session_dep
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/uploads",
                data={
                    "kb_id": "kb-1",
                    "workspace_slug": "pi-lab",
                    "research_project_id": "11111111-1111-1111-1111-111111111111",
                    "chain_node_id": "22222222-2222-2222-2222-222222222222",
                },
                files={"file": ("paper.pdf", b"pdf", "application/pdf")},
            )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["workspace_slug"] == "pi-lab"
        assert payload["research_project_id"] == "11111111-1111-1111-1111-111111111111"
        assert payload["chain_node_id"] == "22222222-2222-2222-2222-222222222222"
        assert captured["research_project_id"] == payload["research_project_id"]
    finally:
        app.dependency_overrides.clear()


def test_upload_rejects_partial_research_metadata():
    """课题 metadata 任一项存在时必须三项完整。"""
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        user_id="user-1", username="alice", role="user", status="active", organization="R&D"
    )
    app.dependency_overrides[get_session] = _empty_session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/uploads",
                data={
                    "kb_id": "kb-1",
                    "workspace_slug": "pi-lab",
                },
                files={"file": ("paper.pdf", b"pdf", "application/pdf")},
            )
        assert response.status_code == 422
        assert "research metadata" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


async def _empty_session():
    """空数据库依赖。"""
    yield None
