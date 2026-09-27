"""WeKnora 上传请求构造测试(不发真实请求,验证 FormData 与 metadata 注入)。"""
import json

import pytest

from app.core import weknora


async def test_upload_file_injects_uploader_metadata(monkeypatch):
    """上传时 metadata 字段必须包含 uploader_id/uploader_name/uploader_org。"""
    captured: dict = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "data": {"id": "k-1", "parse_status": "processing"},
                "success": True,
            }

    async def fake_post(self, url, **kwargs):
        captured["url"] = url
        captured["data"] = kwargs.get("data")
        captured["files"] = kwargs.get("files")
        return FakeResp()

    monkeypatch.setattr(httpx_client_class(), "post", fake_post)

    # AUTH_SECRET 等环境变量已经在 .env 中,无需额外设置
    result = await weknora.upload_file(
        kb_id="kb-1",
        file_bytes=b"hello",
        file_name="report.pdf",
        file_size=5,
        uploader_user_id="u1",
        uploader_username="alice",
        uploader_organization="R&D",
        custom_filename="sub/report.pdf",
    )

    assert result["id"] == "k-1"
    assert result["task_id"] == "k-1"
    metadata_raw = captured["data"].get("metadata")
    meta = json.loads(metadata_raw)
    assert meta["uploader_id"] == "u1"
    assert meta["uploader_name"] == "alice"
    assert meta["uploader_org"] == "R&D"
    assert "org_unit_id" not in meta
    assert captured["data"].get("fileName") == "sub/report.pdf"
    assert captured["files"]["file"][0] == "report.pdf"
    # files 第二项可能是 bytes 或 file-like
    file_obj = captured["files"]["file"][1]
    if hasattr(file_obj, "read"):
        # 若是 SpooledTemporaryFile 之类
        assert file_obj.read() == b"hello"
    else:
        assert file_obj == b"hello"


async def test_upload_file_raises_on_4xx(monkeypatch):
    """4xx 响应抛 WeknoraError。"""

    class FakeResp:
        status_code = 400

        def json(self):
            return {"detail": "invalid file type"}

    async def fake_post(self, url, **kwargs):
        return FakeResp()

    monkeypatch.setattr(httpx_client_class(), "post", fake_post)

    with pytest.raises(weknora.WeknoraError) as exc:
        await weknora.upload_file(
            kb_id="kb-1", file_bytes=b"x", file_name="x.txt", file_size=1,
            uploader_user_id="u1", uploader_username="alice",
        )
    assert exc.value.status == 400


async def test_upload_file_raises_on_duplicate_409(monkeypatch):
    """409 文件重复抛 WeknoraError,供上层判断是否落 SQLite。"""

    class FakeResp:
        status_code = 409

        def json(self):
            return {"detail": "duplicate"}

    async def fake_post(self, url, **kwargs):
        return FakeResp()

    monkeypatch.setattr(httpx_client_class(), "post", fake_post)

    with pytest.raises(weknora.WeknoraError) as exc:
        await weknora.upload_file(
            kb_id="kb-1", file_bytes=b"x", file_name="x.txt", file_size=1,
            uploader_user_id="u1", uploader_username="alice",
        )
    assert exc.value.status == 409


async def test_handle_upload_translates_weknora_auth_failure(monkeypatch):
    """WeKnora 401 must surface as a Chinese 401 business error."""
    from io import BytesIO

    from starlette.datastructures import UploadFile

    from app.core.weknora import WeknoraError
    from app.services import upload_service

    async def invalid_key(_kb_id: str) -> bool:
        raise WeknoraError(401, "拉取知识库列表失败")

    monkeypatch.setattr(upload_service, "is_kb_allowed", invalid_key)
    upload = UploadFile(file=BytesIO(b"paper"), filename="paper.md", headers=None)

    try:
        await upload_service.handle_upload(
            session=None,
            kb_id="kb-1",
            file=upload,
            uploader_user_id="u1",
            uploader_username="alice",
            uploader_organization="",
            max_size_bytes=1024,
            allowed_types={"md"},
        )
    except upload_service.UploadError as exc:
        assert exc.status_code == 401
        assert "认证失败" in exc.message
    else:
        raise AssertionError("WeKnora auth failure should be translated")


def test_kb_list_translates_weknora_auth_failure(monkeypatch):
    """The KB-list BFF also returns a Chinese 401 business response."""
    from fastapi.testclient import TestClient

    from app.api.v1.auth import UserInfo, get_current_user
    from app.api.v1 import kb as kb_api
    from app.core.weknora import WeknoraError
    from app.main import app

    async def invalid_key(refresh: bool = False):
        raise WeknoraError(401, "拉取知识库列表失败")

    monkeypatch.setattr(kb_api, "get_kb_list", invalid_key)
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        user_id="user-1", username="alice", role="user", status="active"
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/kb/list")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert "认证失败" in response.json()["detail"]


def httpx_client_class():
    """返回 httpx.AsyncClient 类(供 monkeypatch 用)。"""
    import httpx
    return httpx.AsyncClient


async def test_upload_file_forwards_group_metadata(monkeypatch):
    """完整小组追溯字段写入 WeKnora metadata，缺省字段不写入。"""
    captured: dict = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"data": {"id": "k-2", "parse_status": "pending"}, "success": True}

    async def fake_post(self, url, **kwargs):
        captured["data"] = kwargs.get("data")
        return FakeResp()

    monkeypatch.setattr(httpx_client_class(), "post", fake_post)
    await weknora.upload_file(
        kb_id="kb-team",
        file_bytes=b"hello",
        file_name="paper.md",
        file_size=5,
        uploader_user_id="u1",
        uploader_username="alice",
        uploader_organization="R&D",
        research_metadata={
            "workspace_slug": "pi-lab",
            "research_project_id": "11111111-1111-1111-1111-111111111111",
            "chain_node_id": "22222222-2222-2222-2222-222222222222",
            "org_unit_id": "33333333-3333-3333-3333-333333333333",
            "org_unit_name": "电池",
            "chain_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "unused": "",
        },
    )
    meta = json.loads(captured["data"]["metadata"])
    assert meta["org_unit_id"] == "33333333-3333-3333-3333-333333333333"
    assert meta["org_unit_name"] == "电池"
    assert meta["chain_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert meta["workspace_slug"] == "pi-lab"
    assert "unused" not in meta
