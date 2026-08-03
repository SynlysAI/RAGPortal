"""WeKnora 历史回写服务测试。"""
from app.services.backfill_service import (
    SYSTEM_USER_ID,
    SYSTEM_USERNAME,
    UNKNOWN_SOURCE,
    _extract_uploader,
    _parse_metadata,
)


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
