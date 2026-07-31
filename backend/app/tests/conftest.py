"""pytest 共享 fixture。"""
import pytest


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """每个测试前清掉 Settings 缓存,让 monkeypatch.setenv 生效。"""
    from app.core import config
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
