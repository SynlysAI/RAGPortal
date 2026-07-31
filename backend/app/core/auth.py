"""HMAC Token 生成与验签。逻辑与 AI4MS backend/app/core/auth.py 完全一致,确保 SSO 兼容。

Token 格式:``{base64url(payload)}.{hmac_sha256(payload_b64, AUTH_SECRET)}``
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from app.core.config import get_settings


def _get_secret() -> bytes:
    """获取 HMAC 签名密钥(从配置读取)。"""
    return get_settings().auth_secret.encode("utf-8")


def generate_token(payload: dict) -> str:
    """生成 token。

    Args:
        payload: token 载荷,必须包含 sub/username/role/iat/exp。

    Returns:
        token 字符串。
    """
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    sig = hmac.new(_get_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def parse_token(token: str) -> Optional[dict]:
    """校验并解析 token。

    Args:
        token: 完整 token 字符串。

    Returns:
        成功返回 payload 字典,失败返回 None。
    """
    try:
        payload_b64, sig = token.rsplit(".", 1)
    except (ValueError, AttributeError):
        return None
    expected_sig = hmac.new(_get_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        return None
    try:
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return None
    if payload.get("role") not in ("admin", "user"):
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload
