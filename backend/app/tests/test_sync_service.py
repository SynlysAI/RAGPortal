"""懒同步服务测试。"""
from app.services import sync_service
from app.services.sync_service import _map_status


def test_map_status_success_variants():
    """success 家族映射。"""
    for s in ("success", "completed", "enabled", "finalizing", "Success", "Finalizing"):
        status, err = _map_status(s)
        assert status == "success"
        assert err == ""


def test_map_status_processing_variants():
    """processing 家族映射。"""
    for s in ("processing", "reprocessing"):
        status, _ = _map_status(s)
        assert status == "processing"


def test_map_status_failed_variants():
    """failed 家族映射。"""
    for s in ("failed", "error"):
        status, _ = _map_status(s)
        assert status == "failed"


def test_map_status_cancelled_is_failed_with_stable_error():
    """WeKnora 取消是失败终态，不能落入 pending 无限等待。"""
    status, err = _map_status("cancelled")
    assert status == "failed"
    assert err == "上游文档处理已取消"


async def test_sync_one_preserves_cancelled_error(monkeypatch):
    """懒同步不会用空的上游 error message 覆盖取消说明。"""

    class _Session:
        async def commit(self):
            """测试用空提交。"""

    upload = sync_service.Upload(
        id=1,
        knowledge_id="k-cancelled",
        kb_id="kb-1",
        kb_name="测试知识库",
        uploader_user_id="u1",
        uploader_username="alice",
        uploader_organization="R&D",
        file_name="report.pdf",
        file_type="pdf",
        file_size=1,
        file_hash="",
        parse_status="processing",
        parse_error="",
        weknora_task_id="",
        uploaded_at="2026-11-04T00:00:00+08:00",
        last_synced_at="",
    )

    async def fake_get_knowledge(_knowledge_id):
        """返回已取消但未提供错误消息的 WeKnora 文档。"""
        return {"parse_status": "cancelled", "error_message": "", "file_hash": ""}

    monkeypatch.setattr(sync_service, "get_knowledge", fake_get_knowledge)
    await sync_service.sync_one(_Session(), upload)

    assert upload.parse_status == "failed"
    assert upload.parse_error == "上游文档处理已取消"


def test_map_status_unknown_falls_back_to_pending():
    """未知状态映射为 pending。"""
    status, _ = _map_status("weird_status")
    assert status == "pending"


def test_map_status_deleted_is_terminal():
    """上游显式 deleted 状态保持终止态。"""
    status, err = _map_status("deleted")
    assert status == "deleted"
    assert err == "上游文档已删除"
