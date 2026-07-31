"""懒同步服务测试。"""
from app.services.sync_service import _map_status


def test_map_status_success_variants():
    """success 家族映射。"""
    for s in ("success", "completed", "enabled", "Success"):
        status, err = _map_status(s)
        assert status == "success"
        assert err == ""


def test_map_status_processing_variants():
    """processing 家族映射。"""
    for s in ("processing", "finalizing", "reprocessing"):
        status, _ = _map_status(s)
        assert status == "processing"


def test_map_status_failed_variants():
    """failed 家族映射。"""
    for s in ("failed", "error"):
        status, _ = _map_status(s)
        assert status == "failed"


def test_map_status_unknown_falls_back_to_pending():
    """未知状态映射为 pending。"""
    status, _ = _map_status("weird_status")
    assert status == "pending"
