"""KB 列表缓存服务测试。"""
import pytest

from app.services import kb_service


@pytest.fixture(autouse=True)
def _reset_cache():
    """每个用例前后清空缓存。"""
    kb_service.clear_cache()
    yield
    kb_service.clear_cache()


async def test_get_kb_list_caches_until_ttl():
    """TTL 内不重复调用 weknora。"""
    call_count = {"n": 0}

    async def fake_list():
        call_count["n"] += 1
        return [{"id": "kb1", "name": "KB1", "type": "document"}]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(kb_service, "list_knowledge_bases", fake_list)
        await kb_service.get_kb_list()
        await kb_service.get_kb_list()
        await kb_service.get_kb_list()

    assert call_count["n"] == 1


async def test_get_kb_list_refresh_bypasses_cache():
    """refresh=True 强制刷新。"""
    call_count = {"n": 0}

    async def fake_list():
        call_count["n"] += 1
        return [{"id": "kb1", "name": "KB1", "type": "document"}]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(kb_service, "list_knowledge_bases", fake_list)
        await kb_service.get_kb_list()
        await kb_service.get_kb_list(refresh=True)

    assert call_count["n"] == 2


async def test_is_kb_allowed_refreshes_on_miss():
    """首次 miss 时自动刷新一次。"""
    seq = iter([
        [{"id": "kb1", "name": "KB1", "type": "document"}],
        [
            {"id": "kb1", "name": "KB1", "type": "document"},
            {"id": "kb2", "name": "KB2", "type": "document"},
        ],
    ])

    async def fake_list():
        return next(seq)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(kb_service, "list_knowledge_bases", fake_list)
        assert await kb_service.is_kb_allowed("kb2") is True


async def test_is_kb_allowed_false_when_absent():
    """刷新后仍不存在则返回 False。"""
    async def fake_list():
        return [{"id": "kb1", "name": "KB1", "type": "document"}]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(kb_service, "list_knowledge_bases", fake_list)
        assert await kb_service.is_kb_allowed("kbX") is False
