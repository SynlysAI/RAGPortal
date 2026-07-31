"""HMAC token 验签逻辑测试。"""
import time

import pytest

from app.core.auth import generate_token, parse_token


def _make_payload(user_id="u1", username="alice", role="user", exp_delta=3600):
    """构造测试用 payload。"""
    return {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_delta,
    }


def test_round_trip_valid_token(monkeypatch):
    """生成的 token 能被正确解析。"""
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    token = generate_token(_make_payload())
    payload = parse_token(token)
    assert payload is not None
    assert payload["sub"] == "u1"
    assert payload["username"] == "alice"
    assert payload["role"] == "user"


def test_reject_tampered_signature(monkeypatch):
    """签名被篡改后拒绝。"""
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    token = generate_token(_make_payload())
    payload_b64, _ = token.rsplit(".", 1)
    tampered = f"{payload_b64}.{'0' * 64}"
    assert parse_token(tampered) is None


def test_reject_expired_token(monkeypatch):
    """过期 token 拒绝。"""
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    payload = _make_payload(exp_delta=-10)
    token = generate_token(payload)
    assert parse_token(token) is None


def test_reject_invalid_role(monkeypatch):
    """role 字段非 admin/user 拒绝。"""
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    payload = _make_payload(role="superuser")
    token = generate_token(payload)
    assert parse_token(token) is None


def test_reject_wrong_secret(monkeypatch):
    """不同 AUTH_SECRET 签发的 token 拒绝。"""
    from app.core import config

    monkeypatch.setenv("AUTH_SECRET", "secret-a")
    config.get_settings.cache_clear()
    token = generate_token(_make_payload())

    monkeypatch.setenv("AUTH_SECRET", "secret-b")
    config.get_settings.cache_clear()
    assert parse_token(token) is None
