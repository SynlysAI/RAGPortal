"""前端 SPA 静态托管回退测试。"""
from fastapi.testclient import TestClient

from app.main import app


def test_spa_route_falls_back_to_index_html():
    """非 API 前端路由应回退到 index.html。"""
    with TestClient(app) as client:
        response = client.get("/my-uploads")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "<div id=\"root\"></div>" in response.text
