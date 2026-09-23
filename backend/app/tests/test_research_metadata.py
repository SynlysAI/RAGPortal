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
            weknora_task_id="task-1",
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
                    "file_sha256": "a" * 64,
                },
                files={"file": ("paper.pdf", b"pdf", "application/pdf")},
            )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["workspace_slug"] == "pi-lab"
        assert payload["research_project_id"] == "11111111-1111-1111-1111-111111111111"
        assert payload["chain_node_id"] == "22222222-2222-2222-2222-222222222222"
        assert payload["task_id"] == "task-1"
        assert captured["research_project_id"] == payload["research_project_id"]
        assert captured["file_sha256"] == "a" * 64
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


async def test_upload_rejects_sha256_mismatch(monkeypatch):
    """metadata sha256 与实际文件不一致时必须在调用 WeKnora 前拒绝。"""
    from io import BytesIO

    from starlette.datastructures import UploadFile

    from app.services import upload_service

    async def allowed_kb(_kb_id: str) -> bool:
        """测试中允许任意 KB。"""
        return True

    async def find_kb(_kb_id: str):
        """测试中不需要 KB 名称。"""
        return {}

    monkeypatch.setattr(upload_service, "is_kb_allowed", allowed_kb)
    monkeypatch.setattr(upload_service, "find_kb", find_kb)
    upload = UploadFile(file=BytesIO(b"different"), filename="paper.md", headers=None)

    try:
        await upload_service.handle_upload(
            session=None,
            kb_id="kb-1",
            file=upload,
            uploader_user_id="u1",
            uploader_username="alice",
            uploader_organization="R&D",
            file_sha256="b" * 64,
            max_size_bytes=1024,
            allowed_types={"md"},
        )
    except upload_service.UploadError as exc:
        assert exc.status_code == 400
        assert "sha256" in exc.message
    else:
        raise AssertionError("sha256 mismatch should be rejected")
