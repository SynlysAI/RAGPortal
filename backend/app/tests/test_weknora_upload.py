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
    metadata_raw = captured["data"].get("metadata")
    meta = json.loads(metadata_raw)
    assert meta["uploader_id"] == "u1"
    assert meta["uploader_name"] == "alice"
    assert meta["uploader_org"] == "R&D"
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


def httpx_client_class():
    """返回 httpx.AsyncClient 类(供 monkeypatch 用)。"""
    import httpx
    return httpx.AsyncClient
