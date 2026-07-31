# RAGPortal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build RAGPortal — a standalone web app for uploading documents to WeKnora knowledge bases, authenticating via AI4MS SSO, tracking uploaders for admin queries.

**Architecture:** BFF pattern. Frontend (React+Vite+TS) → Backend (FastAPI) → WeKnora (REST with `X-API-Key`). Backend reuses AI4MS HMAC token verification (shared `AUTH_SECRET`). No changes to WeKnora or AI4MS.

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind + Zustand + React Router 7 + Axios + Recharts / Python 3.11 + FastAPI + SQLAlchemy 2 (async) + aiosqlite + httpx + Pydantic v2.

**Spec:** `docs/superpowers/specs/2026-07-31-ragportal-design.md`

**Project location:** `E:\github_project\RAGPortal` (created fresh in Task 1)

---

## Phase Overview

| Phase | Tasks | Outcome |
|-------|-------|---------|
| 1. Backend skeleton | 1–4 | Project layout, config, DB schema, HMAC verification |
| 2. Auth | 5 | `/api/auth/login`, `/api/auth/me`, `/api/config` |
| 3. WeKnora client | 6–8 | KB list, upload proxy, status sync |
| 4. Business APIs | 9–12 | Upload + my-uploads + admin APIs |
| 5. Frontend skeleton | 13–16 | Vite/React/Tailwind, routing, auth pages |
| 6. Frontend core | 17–18 | Upload page, my-uploads page |
| 7. Admin frontend | 19–20 | Dashboard + admin uploads list |
| 8. Deployment | 21 | pm2 config + README |

Tests written only for: HMAC verification, WeKnora client (request building, status mapping), upload service (double-write logic). API routes & React components: manual verification.

---

## Phase 1: Backend Skeleton

### Task 1: Initialize project structure

**Files:**
- Create: `E:\github_project\RAGPortal\README.md`
- Create: `E:\github_project\RAGPortal\.gitignore`
- Create: `E:\github_project\RAGPortal\.env.example`
- Create: `E:\github_project\RAGPortal\backend\requirements.txt`
- Create: `E:\github_project\RAGPortal\backend\pyproject.toml`
- Create: `E:\github_project\RAGPortal\backend\app\__init__.py` (empty)

- [ ] **Step 1: Create directory tree**

```bash
mkdir -p E:/github_project/RAGPortal/backend/app/{core,models,api/v1,services,tests}
mkdir -p E:/github_project/RAGPortal/backend/data
mkdir -p E:/github_project/RAGPortal/frontend
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
venv/
.venv/
env/

# Env
.env
.env.local

# Data
backend/data/*.db
backend/data/*.db-journal
backend/data/*.db-wal
backend/data/*.db-shm

# Node
node_modules/
dist/
.vite/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Write `.env.example`**

```dotenv
# ===== 认证(与 AI4MS 共享)=====
AUTH_SECRET=replace_with_ai4ms_auth_secret
AUTH_TOKEN_EXPIRE_HOURS=24

# ===== AI4MS 门户对接 =====
AI4MS_BASE_URL=https://ai4ms.wumiaox.com
AI4MS_PORTAL_URL=https://ai4ms.wumiaox.com

# ===== WeKnora 对接 =====
WEKNORA_BASE_URL=https://weknora.wumiaox.com
WEKNORA_API_KEY=replace_with_scoped_api_key

# ===== 上传限制 =====
UPLOAD_MAX_SIZE_MB=100
UPLOAD_CONCURRENCY=5
ALLOWED_FILE_TYPES=pdf,doc,docx,xls,xlsx,ppt,pptx,md,txt,csv,html

# ===== 缓存 =====
KB_LIST_CACHE_TTL=300

# ===== 数据库 =====
SQLITE_PATH=data/ragportal.db

# ===== CORS =====
FRONTEND_ORIGIN=http://localhost:3002

# ===== 部署 =====
APP_ENV=development
LOG_LEVEL=INFO
```

- [ ] **Step 4: Write `backend/requirements.txt`**

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0
httpx==0.28.1
pydantic==2.10.4
pydantic-settings==2.7.0
python-multipart==0.0.20
itsdangerous==2.2.0
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 5: Write `backend/pyproject.toml`**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["app/tests"]
```

- [ ] **Step 6: Write a minimal `README.md`**

```markdown
# RAGPortal

AI4MS 子应用 — 独立的知识库文档上传门户。

- 前端:React + Vite + TypeScript(`frontend/`)
- 后端:Python + FastAPI(`backend/`)
- 认证:复用 AI4MS HMAC Token(共享 `AUTH_SECRET`)
- 文档存储:WeKnora(通过 `X-API-Key` 调用)

详见 `docs/specs/`。

## 本地开发

```bash
# 后端
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
cp ../.env.example ../.env  # 修改其中的密钥
uvicorn app.main:app --reload --port 8002

# 前端
cd frontend
npm install
npm run dev  # 默认 3002 端口
```
```

- [ ] **Step 7: Initialize git & commit**

```bash
cd E:/github_project/RAGPortal
git init
git add .
git commit -m "init: scaffold RAGPortal project skeleton"
```

---

### Task 2: FastAPI entry + Pydantic Settings + health check

**Files:**
- Create: `backend/app/core/__init__.py` (empty)
- Create: `backend/app/core/config.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py` (empty)
- Create: `backend/app/api/v1/__init__.py` (empty)

- [ ] **Step 1: Create virtualenv and install deps**

```bash
cd E:/github_project/RAGPortal/backend
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
```

- [ ] **Step 2: Write `backend/app/core/config.py`**

```python
"""应用配置,从环境变量加载。"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """RAGPortal 全局配置。"""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 认证
    auth_secret: str
    auth_token_expire_hours: int = 24

    # AI4MS
    ai4ms_base_url: str
    ai4ms_portal_url: str

    # WeKnora
    weknora_base_url: str
    weknora_api_key: str

    # 上传
    upload_max_size_mb: int = 100
    upload_concurrency: int = 5
    allowed_file_types: str = "pdf,doc,docx,xls,xlsx,ppt,pptx,md,txt,csv,html"

    # 缓存
    kb_list_cache_ttl: int = 300

    # 数据库
    sqlite_path: str = "data/ragportal.db"

    # CORS
    frontend_origin: str = "http://localhost:3002"

    # 部署
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def allowed_file_types_set(self) -> set[str]:
        """允许的文件扩展名集合(去空白、去前置点)。"""
        return {t.strip().lower().lstrip(".") for t in self.allowed_file_types.split(",") if t.strip()}


@lru_cache
def get_settings() -> Settings:
    """单例 Settings。"""
    return Settings()
```

- [ ] **Step 3: Write `backend/app/main.py`**

```python
"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库。"""
    await init_db()
    yield


def create_app() -> FastAPI:
    """构建 FastAPI 实例。"""
    settings = get_settings()
    app = FastAPI(
        title="RAGPortal",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()


@app.get("/api/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}
```

- [ ] **Step 4: Stub `backend/app/core/db.py` so the app can boot (real schema in Task 3)**

```python
"""数据库初始化占位,Task 3 中替换为完整实现。"""
async def init_db() -> None:
    """占位:Task 3 实现。"""
    return None
```

- [ ] **Step 5: Verify the server boots**

```bash
cd E:/github_project/RAGPortal/backend
source venv/Scripts/activate
uvicorn app.main:app --reload --port 8002
```

In a separate terminal:
```bash
curl http://127.0.0.1:8002/api/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit**

```bash
cd E:/github_project/RAGPortal
git add backend/
git commit -m "feat(backend): FastAPI entry + Pydantic Settings + health check"
```

---

### Task 3: SQLite schema + SQLAlchemy models

**Files:**
- Create: `backend/app/models/__init__.py` (empty)
- Create: `backend/app/models/upload.py`
- Modify: `backend/app/core/db.py` (replace stub)

- [ ] **Step 1: Write `backend/app/models/upload.py`**

```python
"""上传记录 ORM 模型。"""
from datetime import datetime

from sqlalchemy import Integer, String, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""


class Upload(Base):
    """文档上传记录。每条记录对应 WeKnora 中一个 knowledge 条目。"""

    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    kb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kb_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uploader_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    uploader_username: Mapped[str] = mapped_column(String(128), nullable=False)
    uploader_organization: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    parse_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    weknora_task_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    uploaded_at: Mapped[str] = mapped_column(String(32), nullable=False)
    last_synced_at: Mapped[str] = mapped_column(String(32), default="", nullable=False)

    __table_args__ = (
        Index("idx_uploads_user_time", "uploader_user_id", "uploaded_at"),
        Index("idx_uploads_kb_time", "kb_id", "uploaded_at"),
        Index("idx_uploads_status", "parse_status"),
        Index("idx_uploads_time", "uploaded_at"),
    )
```

- [ ] **Step 2: Replace `backend/app/core/db.py` with full implementation**

```python
"""数据库连接与初始化。"""
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.upload import Base


def _build_url() -> str:
    """根据配置生成 SQLAlchemy aiosqlite 连接串。"""
    path = Path(get_settings().sqlite_path)
    if not path.is_absolute():
        # 相对路径相对于 backend/ 目录解析
        path = Path(__file__).resolve().parent.parent.parent / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{path.as_posix()}"


engine = create_async_engine(_build_url(), echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """启动时建表。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI 依赖:提供数据库会话。"""
    async with async_session() as session:
        yield session
```

- [ ] **Step 3: Verify table creation**

Restart uvicorn, then:

```bash
cd E:/github_project/RAGPortal/backend
python -c "import asyncio; from app.core.db import init_db; asyncio.run(init_db())"
sqlite3 data/ragportal.db ".schema uploads"
```

Expected: schema printed with all columns and indexes.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/ backend/app/core/db.py
git commit -m "feat(backend): SQLite schema + Upload ORM model"
```

---

### Task 4: HMAC token verification + tests

**Files:**
- Create: `backend/app/core/auth.py`
- Create: `backend/app/tests/__init__.py` (empty)
- Create: `backend/app/tests/test_auth.py`

- [ ] **Step 1: Write the failing test `backend/app/tests/test_auth.py`**

```python
"""HMAC token 验签逻辑测试。"""
import time

import pytest

from app.core.auth import generate_token, parse_token


def _make_payload(user_id="u1", username="alice", role="user", exp_delta=3600):
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
    monkeypatch.setenv("AUTH_SECRET", "secret-a")
    token = generate_token(_make_payload())
    monkeypatch.setenv("AUTH_SECRET", "secret-b")
    assert parse_token(token) is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd E:/github_project/RAGPortal/backend
source venv/Scripts/activate
pytest app/tests/test_auth.py -v
```

Expected: all tests FAIL with ImportError (`generate_token` not defined).

- [ ] **Step 3: Implement `backend/app/core/auth.py`**

```python
"""HMAC Token 生成与验签。逻辑与 AI4MS backend/app/core/auth.py 完全一致,确保 SSO 兼容。"""
import base64
import hashlib
import hmac
import json
from typing import Optional

from app.core.config import get_settings


def _get_secret() -> bytes:
    """获取 HMAC 签名密钥(从配置)。"""
    return get_settings().auth_secret.encode("utf-8")


def generate_token(payload: dict) -> str:
    """生成 token,格式:`{base64url(payload)}.{hmac_sha256}`。

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
        import time
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return None
    if payload.get("role") not in ("admin", "user"):
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload
```

Note: `get_settings` reads `AUTH_SECRET` from `.env`. Tests use `monkeypatch.setenv` — but `get_settings` is `@lru_cache`d, so tests must clear the cache. Add a fixture:

Append to `backend/app/tests/test_auth.py`:

```python
@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """每个测试前清掉 Settings 缓存,让 monkeypatch 生效。"""
    from app.core import config
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest app/tests/test_auth.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/auth.py backend/app/tests/
git commit -m "feat(backend): HMAC token verification (parity with AI4MS)"
```

---

## Phase 2: Auth

### Task 5: FastAPI auth dependency + `/api/auth/*` + `/api/config`

**Files:**
- Create: `backend/app/api/v1/auth.py`
- Create: `backend/app/api/v1/config.py`
- Modify: `backend/app/main.py` (register routers)

- [ ] **Step 1: Write `backend/app/api/v1/auth.py`**

```python
"""认证相关路由:登录代理 / 当前用户 / 退出。"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from httpx import AsyncClient
from pydantic import BaseModel

from app.core.auth import parse_token
from app.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """登录请求体。"""

    username: str
    password: str


class UserInfo(BaseModel):
    """对前端暴露的用户信息。"""

    user_id: str
    username: str
    role: str
    status: str = "active"
    organization: str = ""


async def get_current_user(request: Request) -> UserInfo:
    """FastAPI 依赖:从 Authorization header 解析当前用户。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    token = auth[7:]
    payload = parse_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return UserInfo(
        user_id=payload["sub"],
        username=payload["username"],
        role=payload["role"],
        status="active",
        organization=payload.get("organization", ""),
    )


async def get_current_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """FastAPI 依赖:仅允许 admin。"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@router.post("/login")
async def login(body: LoginRequest) -> JSONResponse:
    """代理 AI4MS 登录接口。"""
    settings = get_settings()
    async with AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{settings.ai4ms_base_url}/auth/login",
            json={"username": body.username, "password": body.password},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", "登录失败"))
    data = resp.json()
    return JSONResponse(content=data)


@router.get("/me")
async def me(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """返回当前用户信息。"""
    return user


@router.post("/logout")
async def logout() -> dict:
    """退出(无服务端态,前端清 token 即可)。"""
    return {"ok": True}
```

- [ ] **Step 2: Write `backend/app/api/v1/config.py`**

```python
"""前端公共配置接口。"""
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def get_public_config() -> dict:
    """返回前端需要的非敏感配置。"""
    s = get_settings()
    return {
        "portal_url": s.ai4ms_portal_url,
        "max_size_mb": s.upload_max_size_mb,
        "allowed_file_types": sorted(s.allowed_file_types_set),
    }
```

- [ ] **Step 3: Modify `backend/app/main.py` to register routers**

Replace the file with:

```python
"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.config import router as config_router
from app.core.config import get_settings
from app.core.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库。"""
    await init_db()
    yield


def create_app() -> FastAPI:
    """构建 FastAPI 实例。"""
    settings = get_settings()
    app = FastAPI(title="RAGPortal", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(config_router)
    return app


app = create_app()


@app.get("/api/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}
```

- [ ] **Step 4: Manual verification**

```bash
# 启动后端(确保 .env 里 AUTH_SECRET 与 AI4MS 一致)
cd E:/github_project/RAGPortal/backend
uvicorn app.main:app --reload --port 8002

# 测试 /api/config(无需登录)
curl http://127.0.0.1:8002/api/config

# 测试 /api/auth/me(无 token 应 401)
curl -i http://127.0.0.1:8002/api/auth/me

# 生成一个本地测试 token
python -c "
import time, json, base64, hmac, hashlib
from app.core.config import get_settings
secret = get_settings().auth_secret.encode()
payload = {'sub':'u1','username':'alice','role':'admin','iat':int(time.time()),'exp':int(time.time())+3600}
b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
sig = hmac.new(secret, b64.encode(), hashlib.sha256).hexdigest()
print(f'{b64}.{sig}')
" | xargs -I{} curl -i -H "Authorization: Bearer {}" http://127.0.0.1:8002/api/auth/me
```

Expected: `/api/config` returns JSON; `/api/auth/me` returns 401 without token, 200 with token.

- [ ] **Step 5: Commit**

```bash
git add backend/app/
git commit -m "feat(backend): auth routes (login proxy, me, logout) + public config"
```

---

## Phase 3: WeKnora Client

### Task 6: WeKnora HTTP client + KB list (with cache) + tests

**Files:**
- Create: `backend/app/core/weknora.py`
- Create: `backend/app/services/__init__.py` (empty)
- Create: `backend/app/services/kb_service.py`
- Create: `backend/app/tests/test_kb_service.py`

- [ ] **Step 1: Write `backend/app/core/weknora.py`**

```python
"""WeKnora HTTP 客户端。"""
from typing import Any, Optional

import httpx

from app.core.config import get_settings


class WeknoraError(Exception):
    """WeKnora API 错误。"""

    def __init__(self, status: int, message: str, payload: Optional[dict] = None):
        super().__init__(f"[{status}] {message}")
        self.status = status
        self.message = message
        self.payload = payload or {}


def _client() -> httpx.AsyncClient:
    """构造带 API Key 的 client。"""
    s = get_settings()
    return httpx.AsyncClient(
        base_url=s.weknora_base_url,
        headers={"X-API-Key": s.weknora_api_key},
        timeout=30,
    )


async def list_knowledge_bases() -> list[dict[str, Any]]:
    """获取当前 API Key 能访问的所有知识库。

    Returns:
        KB 字典列表,每个含 id/name/type 等字段。
    """
    async with _client() as c:
        resp = await c.get("/api/v1/knowledge-bases")
    if resp.status_code != 200:
        raise WeknoraError(resp.status_code, "拉取知识库列表失败", _safe_json(resp))
    data = resp.json()
    items = data.get("data") or data.get("items") or data
    if not isinstance(items, list):
        return []
    return [{"id": kb.get("id"), "name": kb.get("name"), "type": kb.get("type", "document")}
            for kb in items]


async def get_knowledge(knowledge_id: str) -> dict[str, Any]:
    """查询单个 knowledge 的最新状态。"""
    async with _client() as c:
        resp = await c.get(f"/api/v1/knowledge/{knowledge_id}")
    if resp.status_code != 200:
        raise WeknoraError(resp.status_code, "查询文档状态失败", _safe_json(resp))
    data = resp.json()
    return data.get("data") or data


def _safe_json(resp: httpx.Response) -> dict:
    """安全解析响应 JSON。"""
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}
```

- [ ] **Step 2: Write `backend/app/services/kb_service.py`**

```python
"""知识库列表服务:5 分钟内存缓存。"""
import time
from typing import Any

from app.core.config import get_settings
from app.core.weknora import list_knowledge_bases

_cache: dict[str, Any] = {"data": [], "expires_at": 0.0}


async def get_kb_list(refresh: bool = False) -> list[dict[str, Any]]:
    """获取 KB 列表(命中缓存则直接返回)。

    Args:
        refresh: 是否强制刷新。

    Returns:
        KB 字典列表。
    """
    ttl = get_settings().kb_list_cache_ttl
    now = time.time()
    if not refresh and _cache["expires_at"] > now:
        return _cache["data"]
    data = await list_knowledge_bases()
    _cache["data"] = data
    _cache["expires_at"] = now + ttl
    return data


async def is_kb_allowed(kb_id: str) -> bool:
    """检查 kb_id 是否在 API Key 允许范围内。

    若缓存未命中,会自动刷新一次。
    """
    kbs = await get_kb_list()
    if any(kb["id"] == kb_id for kb in kbs):
        return True
    # 缓存可能未预热,刷新一次再判断
    kbs = await get_kb_list(refresh=True)
    return any(kb["id"] == kb_id for kb in kbs)


async def find_kb(kb_id: str) -> dict[str, Any] | None:
    """从缓存中查找 KB,返回 {id, name, type}。"""
    kbs = await get_kb_list()
    for kb in kbs:
        if kb["id"] == kb_id:
            return kb
    kbs = await get_kb_list(refresh=True)
    for kb in kbs:
        if kb["id"] == kb_id:
            return kb
    return None


def clear_cache() -> None:
    """清缓存(测试用)。"""
    _cache["data"] = []
    _cache["expires_at"] = 0.0
```

- [ ] **Step 3: Write the failing test `backend/app/tests/test_kb_service.py`**

```python
"""KB 列表缓存服务测试。"""
import asyncio
from unittest.mock import patch, AsyncMock

import pytest

from app.services import kb_service


@pytest.fixture(autouse=True)
def _reset_cache():
    kb_service.clear_cache()
    yield
    kb_service.clear_cache()


async def test_get_kb_list_caches_until_ttl():
    """TTL 内不重复调用 weknora。"""
    call_count = {"n": 0}

    async def fake_list():
        call_count["n"] += 1
        return [{"id": "kb1", "name": "KB1", "type": "document"}]

    with patch("app.services.kb_service.list_knowledge_bases", new=fake_list):
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

    with patch("app.services.kb_service.list_knowledge_bases", new=fake_list):
        await kb_service.get_kb_list()
        await kb_service.get_kb_list(refresh=True)

    assert call_count["n"] == 2


async def test_is_kb_allowed_refreshes_on_miss():
    """首次 miss 时自动刷新一次。"""
    seq = iter([
        [{"id": "kb1", "name": "KB1", "type": "document"}],
        [{"id": "kb1", "name": "KB1", "type": "document"}, {"id": "kb2", "name": "KB2", "type": "document"}],
    ])

    async def fake_list():
        return next(seq)

    with patch("app.services.kb_service.list_knowledge_bases", new=fake_list):
        assert await kb_service.is_kb_allowed("kb2") is True


async def test_is_kb_allowed_false_when_absent():
    """刷新后仍不存在则返回 False。"""
    async def fake_list():
        return [{"id": "kb1", "name": "KB1", "type": "document"}]

    with patch("app.services.kb_service.list_knowledge_bases", new=fake_list):
        assert await kb_service.is_kb_allowed("kbX") is False
```

- [ ] **Step 4: Run tests**

```bash
pytest app/tests/test_kb_service.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/weknora.py backend/app/services/ backend/app/tests/test_kb_service.py
git commit -m "feat(backend): WeKnora HTTP client + KB list with 5-min cache"
```

---

### Task 7: WeKnora file upload proxy + tests

**Files:**
- Modify: `backend/app/core/weknora.py` (add `upload_file`)
- Create: `backend/app/tests/test_weknora_upload.py`

- [ ] **Step 1: Write the failing test `backend/app/tests/test_weknora_upload.py`**

```python
"""WeKnora 上传请求构造测试(不真发请求,验证 FormData 与 metadata 注入)。"""
import io
from unittest.mock import patch, AsyncMock

import pytest

from app.core import weknora


async def test_upload_file_injects_uploader_metadata():
    """上传时 metadata 字段必须包含 uploader_id/uploader_name/uploader_org。"""
    captured = {}

    class FakeResp:
        status_code = 200
        def json(self): return {"id": "k-1", "parse_status": "pending"}

    async def fake_post(self, url, **kwargs):
        captured["url"] = url
        captured["data"] = kwargs.get("data")
        captured["files"] = kwargs.get("files")
        return FakeResp()

    with patch("httpx.AsyncClient.post", new=fake_post):
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
    # 验证 metadata 字段含 uploader 信息
    metadata_raw = captured["data"].get("metadata")
    import json
    meta = json.loads(metadata_raw)
    assert meta["uploader_id"] == "u1"
    assert meta["uploader_name"] == "alice"
    assert meta["uploader_org"] == "R&D"
    # custom_filename 走 customFileName 字段
    assert captured["data"].get("customFileName") == "sub/report.pdf"
    # 文件流
    assert captured["files"]["file"][0] == "report.pdf"
    assert captured["files"]["file"][1].read() == b"hello"


async def test_upload_file_raises_on_4xx():
    """4xx 响应抛 WeknoraError。"""
    class FakeResp:
        status_code = 400
        def json(self): return {"detail": "invalid file type"}

    async def fake_post(self, url, **kwargs):
        return FakeResp()

    with patch("httpx.AsyncClient.post", new=fake_post):
        with pytest.raises(weknora.WeknoraError) as exc:
            await weknora.upload_file(
                kb_id="kb-1", file_bytes=b"x", file_name="x.txt", file_size=1,
                uploader_user_id="u1", uploader_username="alice",
            )
    assert exc.value.status == 400


async def test_upload_file_raises_on_duplicate_409():
    """409 文件重复抛 WeknoraError(供上层判断是否落 SQLite)。"""
    class FakeResp:
        status_code = 409
        def json(self): return {"detail": "duplicate"}

    async def fake_post(self, url, **kwargs):
        return FakeResp()

    with patch("httpx.AsyncClient.post", new=fake_post):
        with pytest.raises(weknora.WeknoraError) as exc:
            await weknora.upload_file(
                kb_id="kb-1", file_bytes=b"x", file_name="x.txt", file_size=1,
                uploader_user_id="u1", uploader_username="alice",
            )
    assert exc.value.status == 409
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest app/tests/test_weknora_upload.py -v
```

Expected: ImportError for `upload_file`.

- [ ] **Step 3: Implement `upload_file` — append to `backend/app/core/weknora.py`**

```python
import json as _json
from fastapi import UploadFile


async def upload_file(
    *,
    kb_id: str,
    file_bytes: bytes,
    file_name: str,
    file_size: int,
    uploader_user_id: str,
    uploader_username: str,
    uploader_organization: str = "",
    custom_filename: str = "",
) -> dict[str, Any]:
    """代理 WeKnora 单文件上传。

    Args:
        kb_id: 目标知识库 ID。
        file_bytes: 文件二进制内容。
        file_name: 原始文件名(用于扩展名校验)。
        file_size: 文件大小(字节)。
        uploader_user_id: 上传者 AI4MS user_id。
        uploader_username: 上传者用户名(冗余快照)。
        uploader_organization: 上传者组织(冗余快照)。
        custom_filename: 自定义文件名(文件夹场景含相对路径)。

    Returns:
        WeKnora 返回的 knowledge 对象。

    Raises:
        WeknoraError: WeKnora 返回非 200。
    """
    metadata = {
        "uploader_id": uploader_user_id,
        "uploader_name": uploader_username,
        "uploader_org": uploader_organization,
    }
    data = {"metadata": _json.dumps(metadata)}
    if custom_filename:
        data["customFileName"] = custom_filename
    files = {"file": (file_name, file_bytes)}

    async with _client() as c:
        resp = await c.post(
            f"/api/v1/knowledge-bases/{kb_id}/knowledge/file",
            data=data,
            files=files,
        )
    if resp.status_code not in (200, 201):
        raise WeknoraError(resp.status_code, _safe_json(resp).get("detail", "上传失败"), _safe_json(resp))
    return _safe_json(resp)
```

- [ ] **Step 4: Run tests**

```bash
pytest app/tests/test_weknora_upload.py -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/weknora.py backend/app/tests/test_weknora_upload.py
git commit -m "feat(backend): WeKnora file upload proxy with metadata injection"
```

---

### Task 8: Status mapping + lazy sync service + tests

**Files:**
- Create: `backend/app/services/sync_service.py`
- Create: `backend/app/tests/test_sync_service.py`

- [ ] **Step 1: Write `backend/app/services/sync_service.py`**

```python
"""解析状态懒同步服务。"""
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.weknora import get_knowledge
from app.models.upload import Upload


def _map_status(weknora_status: str) -> tuple[str, str]:
    """WeKnora parse_status 映射到 RAGPortal 状态。

    Args:
        weknora_status: WeKnora 返回的 parse_status 原值。

    Returns:
        (ragportal_status, parse_error)。
    """
    s = (weknora_status or "").lower()
    if s in ("success", "completed", "enabled"):
        return "success", ""
    if s in ("processing", "finalizing", "reprocessing"):
        return "processing", ""
    if s in ("failed", "error"):
        return "failed", ""  # error_message 由调用方注入
    return "pending", ""


async def sync_one(session: AsyncSession, upload: Upload) -> Upload:
    """拉取 WeKnora 单条最新状态并更新到 DB。

    Args:
        session: 异步 DB 会话。
        upload: Upload 记录(已绑定到会话)。

    Returns:
        更新后的 Upload 对象。
    """
    if upload.parse_status in ("success", "failed"):
        return upload
    data = await get_knowledge(upload.knowledge_id)
    weknora_status = data.get("parse_status", "")
    new_status, _ = _map_status(weknora_status)
    error_msg = ""
    if new_status == "failed":
        error_msg = data.get("error_message", "") or data.get("error", "")
    upload.parse_status = new_status
    upload.parse_error = error_msg
    from datetime import datetime, timezone
    upload.last_synced_at = datetime.now(timezone.utc).isoformat()
    await session.commit()
    return upload


async def sync_pending(session: AsyncSession, limit: int = 50) -> int:
    """批量懒同步:对最近 N 条非终态记录拉取最新状态。

    Args:
        session: 异步 DB 会话。
        limit: 最多同步多少条。

    Returns:
        实际同步的记录数。
    """
    stmt = (
        select(Upload)
        .where(Upload.parse_status.in_(("pending", "processing")))
        .order_by(Upload.uploaded_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    uploads = result.scalars().all()
    count = 0
    for upload in uploads:
        try:
            await sync_one(session, upload)
            count += 1
        except Exception:
            # 单条失败不影响其他
            continue
    return count
```

- [ ] **Step 2: Write `backend/app/tests/test_sync_service.py`**

```python
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
```

- [ ] **Step 3: Run tests**

```bash
pytest app/tests/test_sync_service.py -v
```

Expected: all 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/sync_service.py backend/app/tests/test_sync_service.py
git commit -m "feat(backend): parse-status mapping + lazy sync service"
```

---

## Phase 4: Business APIs

### Task 9: Upload service + `POST /api/uploads` (double-write)

**Files:**
- Create: `backend/app/services/upload_service.py`
- Create: `backend/app/api/v1/uploads.py`
- Modify: `backend/app/main.py` (register uploads router)

- [ ] **Step 1: Write `backend/app/services/upload_service.py`**

```python
"""上传业务逻辑:WeKnora 调用 + SQLite 双写。"""
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.weknora import WeknoraError, upload_file as weknora_upload_file
from app.models.upload import Upload
from app.services.kb_service import find_kb, is_kb_allowed


class UploadError(Exception):
    """上传业务错误,带 status_code。"""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _file_extension(filename: str) -> str:
    """提取扩展名(小写无点)。"""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def handle_upload(
    *,
    session: AsyncSession,
    kb_id: str,
    file: UploadFile,
    uploader_user_id: str,
    uploader_username: str,
    uploader_organization: str,
    max_size_bytes: int,
    allowed_types: set[str],
) -> Upload:
    """处理一次上传:校验 → 调 WeKnora → 写 SQLite。

    Raises:
        UploadError: 业务校验失败(权限/大小/类型)。
    """
    # 1. 校验 KB 权限
    if not await is_kb_allowed(kb_id):
        raise UploadError(403, "无权上传到此知识库")
    kb = await find_kb(kb_id)

    # 2. 校验大小
    file_bytes = await file.read()
    if len(file_bytes) > max_size_bytes:
        raise UploadError(413, f"文件超出大小限制({max_size_bytes // (1024 * 1024)}MB)")

    # 3. 校验类型
    ext = _file_extension(file.filename or "")
    if ext not in allowed_types:
        raise UploadError(400, f"不支持的文件类型:{ext}")

    # 4. 调 WeKnora
    try:
        weknora_resp = await weknora_upload_file(
            kb_id=kb_id,
            file_bytes=file_bytes,
            file_name=file.filename or "untitled",
            file_size=len(file_bytes),
            uploader_user_id=uploader_user_id,
            uploader_username=uploader_username,
            uploader_organization=uploader_organization,
            custom_filename=file.filename or "",
        )
    except WeknoraError as e:
        # 409 重复:不写 SQLite,直接抛 UploadError 给前端友好提示
        if e.status == 409:
            raise UploadError(409, "文件已存在") from e
        raise UploadError(e.status, e.message) from e

    knowledge_id = weknora_resp.get("id")
    if not knowledge_id:
        raise UploadError(502, "WeKnora 响应缺少 knowledge id")

    # 5. 写 SQLite
    now = datetime.now(timezone.utc).isoformat()
    record = Upload(
        knowledge_id=knowledge_id,
        kb_id=kb_id,
        kb_name=kb["name"] if kb else "",
        uploader_user_id=uploader_user_id,
        uploader_username=uploader_username,
        uploader_organization=uploader_organization,
        file_name=file.filename or "untitled",
        file_type=ext,
        file_size=len(file_bytes),
        parse_status="pending",
        parse_error="",
        weknora_task_id=weknora_resp.get("task_id", ""),
        uploaded_at=now,
        last_synced_at=now,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
```

- [ ] **Step 2: Write `backend/app/api/v1/uploads.py`**

```python
"""上传与个人历史路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user, UserInfo
from app.core.config import get_settings
from app.core.db import get_session
from app.models.upload import Upload
from app.services.sync_service import sync_one
from app.services.upload_service import UploadError, handle_upload

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _to_dict(u: Upload) -> dict:
    """序列化 Upload 为前端可读字典。"""
    return {
        "id": u.id,
        "knowledge_id": u.knowledge_id,
        "kb_id": u.kb_id,
        "kb_name": u.kb_name,
        "uploader_user_id": u.uploader_user_id,
        "uploader_username": u.uploader_username,
        "uploader_organization": u.uploader_organization,
        "file_name": u.file_name,
        "file_type": u.file_type,
        "file_size": u.file_size,
        "parse_status": u.parse_status,
        "parse_error": u.parse_error,
        "uploaded_at": u.uploaded_at,
    }


@router.post("")
async def upload(
    file: UploadFile = File(...),
    kb_id: str = Form(...),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """上传单个文件到指定 KB。"""
    settings = get_settings()
    try:
        record = await handle_upload(
            session=session,
            kb_id=kb_id,
            file=file,
            uploader_user_id=user.user_id,
            uploader_username=user.username,
            uploader_organization=user.organization,
            max_size_bytes=settings.upload_max_size_mb * 1024 * 1024,
            allowed_types=settings.allowed_file_types_set,
        )
    except UploadError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return _to_dict(record)


@router.get("/mine")
async def list_my_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """当前用户上传记录(按上传时间倒序)。"""
    offset = (page - 1) * page_size
    stmt = (
        select(Upload)
        .where(Upload.uploader_user_id == user.user_id)
        .order_by(Upload.uploaded_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    items = [_to_dict(u) for u in result.scalars().all()]
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/{upload_id}")
async def get_upload(
    upload_id: int,
    user: UserInfo = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """单条记录详情(同时触发该记录的状态懒同步)。"""
    stmt = select(Upload).where(Upload.id == upload_id)
    if user.role != "admin":
        stmt = stmt.where(Upload.uploader_user_id == user.user_id)
    result = await session.execute(stmt)
    upload = result.scalars().first()
    if upload is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    await sync_one(session, upload)
    return _to_dict(upload)
```

- [ ] **Step 3: Modify `backend/app/main.py` to include uploads router**

Add to `main.py` (after the existing `app.include_router(config_router)` line):

```python
from app.api.v1.uploads import router as uploads_router
...
app.include_router(uploads_router)
```

- [ ] **Step 4: Manual verification**

```bash
# 重启后端
# 1) 无 token → 401
curl -i -X POST -F "file=@some.pdf" -F "kb_id=kb1" http://127.0.0.1:8002/api/uploads

# 2) 带伪造 token(把 user role 设为 user)→ 应触发 weknora 调用
# 生成 user token
python -c "
import time, json, base64, hmac, hashlib
from app.core.config import get_settings
secret = get_settings().auth_secret.encode()
payload = {'sub':'u1','username':'alice','role':'user','iat':int(time.time()),'exp':int(time.time())+3600}
b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
sig = hmac.new(secret, b64.encode(), hashlib.sha256).hexdigest()
print(f'{b64}.{sig}')
"
# 用上面的 token + 真实的 KB + 真实文件测试
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/
git commit -m "feat(backend): upload endpoint with double-write (WeKnora + SQLite)"
```

---

### Task 10: KB list endpoint + admin endpoints (list/filter/export/stats)

**Files:**
- Create: `backend/app/api/v1/kb.py`
- Create: `backend/app/api/v1/admin.py`
- Modify: `backend/app/main.py` (register new routers)

- [ ] **Step 1: Write `backend/app/api/v1/kb.py`**

```python
"""知识库列表路由(代理 WeKnora,带缓存)。"""
from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user, UserInfo
from app.services.kb_service import get_kb_list

router = APIRouter(prefix="/api/kb", tags=["kb"])


@router.get("/list")
async def list_kbs(user: UserInfo = Depends(get_current_user)) -> dict:
    """获取当前 API Key 能访问的所有 KB。"""
    items = await get_kb_list()
    return {"items": items}
```

- [ ] **Step 2: Write `backend/app/api/v1/admin.py`**

```python
"""Admin 路由:全部上传记录 / 导出 CSV / 统计。"""
import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.v1.auth import get_current_admin, UserInfo
from app.core.db import get_session
from app.models.upload import Upload
from app.services.sync_service import sync_pending
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _to_admin_dict(u: Upload) -> dict:
    """admin 视角的记录序列化(含上传者完整信息)。"""
    return {
        "id": u.id,
        "knowledge_id": u.knowledge_id,
        "kb_id": u.kb_id,
        "kb_name": u.kb_name,
        "uploader_user_id": u.uploader_user_id,
        "uploader_username": u.uploader_username,
        "uploader_organization": u.uploader_organization,
        "file_name": u.file_name,
        "file_type": u.file_type,
        "file_size": u.file_size,
        "parse_status": u.parse_status,
        "parse_error": u.parse_error,
        "uploaded_at": u.uploaded_at,
    }


def _apply_filters(stmt, uploader: Optional[str], kb_id: Optional[str],
                   status: Optional[str], filename: Optional[str],
                   start: Optional[str], end: Optional[str]):
    """应用筛选条件到 select 语句。"""
    if uploader:
        stmt = stmt.where(Upload.uploader_username.like(f"%{uploader}%"))
    if kb_id:
        stmt = stmt.where(Upload.kb_id == kb_id)
    if status:
        stmt = stmt.where(Upload.parse_status == status)
    if filename:
        stmt = stmt.where(Upload.file_name.like(f"%{filename}%"))
    if start:
        stmt = stmt.where(Upload.uploaded_at >= start)
    if end:
        stmt = stmt.where(Upload.uploaded_at <= end)
    return stmt


@router.get("/uploads")
async def list_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    uploader: Optional[str] = Query(None),
    kb_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    filename: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """全部上传记录(支持筛选与分页)。"""
    base = select(Upload)
    base = _apply_filters(base, uploader, kb_id, status, filename, start, end)
    # count
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    # paged
    stmt = base.order_by(Upload.uploaded_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = [_to_admin_dict(u) for u in (await session.execute(stmt)).scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/uploads/export")
async def export_uploads(
    uploader: Optional[str] = Query(None),
    kb_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    filename: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """按当前筛选条件导出 CSV。"""
    stmt = _apply_filters(select(Upload), uploader, kb_id, status, filename, start, end)
    stmt = stmt.order_by(Upload.uploaded_at.desc())
    rows = (await session.execute(stmt)).scalars().all()

    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM,Excel 中文兼容
    writer = csv.writer(buf)
    writer.writerow([
        "上传者用户名", "组织", "文件名", "知识库", "文件大小(字节)",
        "状态", "失败原因", "上传时间", "WeKnora 文档 ID",
    ])
    for u in rows:
        writer.writerow([
            u.uploader_username, u.uploader_organization, u.file_name,
            u.kb_name, u.file_size, u.parse_status, u.parse_error,
            u.uploaded_at, u.knowledge_id,
        ])
    buf.seek(0)
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=uploads_{now}.csv"},
    )


@router.post("/uploads/sync-status")
async def sync_status(
    limit: int = Query(50, ge=1, le=500),
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """触发批量懒同步(对最近 N 条非终态记录)。"""
    n = await sync_pending(session, limit=limit)
    return {"synced": n}


@router.get("/stats/overview")
async def stats_overview(
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """仪表盘 KPI。"""
    total = (await session.execute(select(func.count(Upload.id)))).scalar_one()
    week_ago = datetime.now(timezone.utc).isoformat()
    # 简化:本周以近 7 天计
    from datetime import timedelta
    week_ago_iso = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    week_count = (await session.execute(
        select(func.count(Upload.id)).where(Upload.uploaded_at >= week_ago_iso)
    )).scalar_one()
    failed = (await session.execute(
        select(func.count(Upload.id)).where(Upload.parse_status == "failed")
    )).scalar_one()
    active_users = (await session.execute(
        select(func.count(func.distinct(Upload.uploader_user_id)))
        .where(Upload.uploaded_at >= week_ago_iso)
    )).scalar_one()
    return {
        "total": total,
        "week_count": week_count,
        "failed": failed,
        "active_users_7d": active_users,
    }


@router.get("/stats/daily-trend")
async def stats_daily_trend(
    days: int = Query(30, ge=1, le=365),
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """近 N 天每日上传量。"""
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    stmt = (
        select(Upload.uploaded_at)
        .where(Upload.uploaded_at >= since)
        .order_by(Upload.uploaded_at.asc())
    )
    timestamps = (await session.execute(stmt)).scalars().all()
    buckets: dict[str, int] = {}
    for ts in timestamps:
        day = ts[:10]
        buckets[day] = buckets.get(day, 0) + 1
    return {"items": [{"date": d, "count": c} for d, c in sorted(buckets.items())]}


@router.get("/stats/top-uploaders")
async def stats_top_uploaders(
    n: int = Query(5, ge=1, le=50),
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Top N 上传者。"""
    stmt = (
        select(
            Upload.uploader_user_id,
            Upload.uploader_username,
            func.count(Upload.id).label("cnt"),
        )
        .group_by(Upload.uploader_user_id, Upload.uploader_username)
        .order_by(func.count(Upload.id).desc())
        .limit(n)
    )
    rows = (await session.execute(stmt)).all()
    return {"items": [{"user_id": r[0], "username": r[1], "count": r[2]} for r in rows]}


@router.get("/stats/kb-distribution")
async def stats_kb_distribution(
    admin: UserInfo = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """各 KB 上传分布。"""
    stmt = (
        select(Upload.kb_id, Upload.kb_name, func.count(Upload.id).label("cnt"))
        .group_by(Upload.kb_id, Upload.kb_name)
        .order_by(func.count(Upload.id).desc())
    )
    rows = (await session.execute(stmt)).all()
    return {"items": [{"kb_id": r[0], "kb_name": r[1], "count": r[2]} for r in rows]}
```

- [ ] **Step 3: Modify `backend/app/main.py` to include new routers**

Add after the existing `uploads_router`:

```python
from app.api.v1.kb import router as kb_router
from app.api.v1.admin import router as admin_router
...
app.include_router(kb_router)
app.include_router(admin_router)
```

- [ ] **Step 4: Manual verification**

```bash
# 用 admin token 调各接口
curl -H "Authorization: Bearer <admin_token>" http://127.0.0.1:8002/api/admin/stats/overview
curl -H "Authorization: Bearer <admin_token>" http://127.0.0.1:8002/api/admin/stats/daily-trend
curl -H "Authorization: Bearer <admin_token>" http://127.0.0.1:8002/api/admin/stats/top-uploaders
curl -H "Authorization: Bearer <admin_token>" http://127.0.0.1:8002/api/admin/stats/kb-distribution
curl -H "Authorization: Bearer <admin_token>" http://127.0.0.1:8002/api/admin/uploads/export -o test.csv
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/
git commit -m "feat(backend): KB list + admin endpoints (filter, export, stats)"
```

---

## Phase 5: Frontend Skeleton

### Task 11: Vite + React + TypeScript + Tailwind init

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`, `frontend/tailwind.config.ts`, `frontend/postcss.config.js`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/index.css`

- [ ] **Step 1: Scaffold Vite project**

```bash
cd E:/github_project/RAGPortal
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom@7 zustand axios recharts react-dropzone
npm install -D tailwindcss@3 postcss autoprefixer @types/node
npx tailwindcss init -p
```

- [ ] **Step 2: Write `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 3002,
    proxy: {
      '/api': 'http://127.0.0.1:8002',
    },
  },
})
```

- [ ] **Step 3: Write `frontend/tsconfig.app.json` (paths)**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Write `frontend/tailwind.config.ts`**

```typescript
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#2563eb',
          dark: '#1d4ed8',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
```

- [ ] **Step 5: Write `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #root {
  height: 100%;
}

body {
  background: #f8fafc;
  color: #0f172a;
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
}
```

- [ ] **Step 6: Write `frontend/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>RAGPortal</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 7: Write minimal `frontend/src/main.tsx`**

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

function App() {
  return <div className="p-8 text-xl">RAGPortal — frontend scaffold OK</div>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 8: Verify dev server**

```bash
cd frontend
npm run dev
# 打开 http://localhost:3002 应看到 "RAGPortal — frontend scaffold OK"
```

- [ ] **Step 9: Commit**

```bash
cd E:/github_project/RAGPortal
git add frontend/
git commit -m "feat(frontend): scaffold Vite + React + TS + Tailwind"
```

---

### Task 12: API client + authStore + router

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/kb.ts`
- Create: `frontend/src/api/uploads.ts`
- Create: `frontend/src/api/admin.ts`
- Create: `frontend/src/stores/authStore.ts`
- Create: `frontend/src/router.tsx`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Write `frontend/src/api/client.ts`**

```typescript
import axios, { AxiosError } from 'axios'

const TOKEN_KEY = 'ai4ms_token'

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

export const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截:自动加 Authorization
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截:401 自动跳登录
api.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearToken()
      // 避免在 /login 自身陷入死循环
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)
```

- [ ] **Step 2: Write `frontend/src/api/auth.ts`**

```typescript
import { api } from './client'

export interface UserInfo {
  user_id: string
  username: string
  role: 'admin' | 'user'
  status: string
  organization: string
}

export interface PublicConfig {
  portal_url: string
  max_size_mb: number
  allowed_file_types: string[]
}

export const authApi = {
  async login(username: string, password: string): Promise<{ token: string; user: UserInfo }> {
    const resp = await api.post('/auth/login', { username, password })
    return resp.data
  },
  async me(): Promise<UserInfo> {
    const resp = await api.get('/auth/me')
    return resp.data
  },
  async getConfig(): Promise<PublicConfig> {
    const resp = await api.get('/config')
    return resp.data
  },
}
```

- [ ] **Step 3: Write `frontend/src/api/kb.ts`**

```typescript
import { api } from './client'

export interface KbInfo {
  id: string
  name: string
  type: string
}

export const kbApi = {
  async list(): Promise<KbInfo[]> {
    const resp = await api.get('/kb/list')
    return resp.data.items
  },
}
```

- [ ] **Step 4: Write `frontend/src/api/uploads.ts`**

```typescript
import { api } from './client'

export interface UploadRecord {
  id: number
  knowledge_id: string
  kb_id: string
  kb_name: string
  uploader_user_id?: string
  uploader_username?: string
  uploader_organization?: string
  file_name: string
  file_type: string
  file_size: number
  parse_status: 'pending' | 'processing' | 'success' | 'failed'
  parse_error: string
  uploaded_at: string
}

export const uploadsApi = {
  async upload(file: File, kbId: string, onProgress?: (pct: number) => void): Promise<UploadRecord> {
    const form = new FormData()
    form.append('file', file)
    form.append('kb_id', kbId)
    const resp = await api.post('/uploads', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
    return resp.data
  },
  async mine(page = 1, pageSize = 20): Promise<{ items: UploadRecord[]; page: number; page_size: number }> {
    const resp = await api.get('/uploads/mine', { params: { page, page_size: pageSize } })
    return resp.data
  },
  async get(id: number): Promise<UploadRecord> {
    const resp = await api.get(`/uploads/${id}`)
    return resp.data
  },
}
```

- [ ] **Step 5: Write `frontend/src/api/admin.ts`**

```typescript
import { api } from './client'
import type { UploadRecord } from './uploads'

export interface AdminListParams {
  page?: number
  page_size?: number
  uploader?: string
  kb_id?: string
  status?: string
  filename?: string
  start?: string
  end?: string
}

export const adminApi = {
  async list(params: AdminListParams): Promise<{ items: UploadRecord[]; total: number; page: number; page_size: number }> {
    const resp = await api.get('/admin/uploads', { params })
    return resp.data
  },
  async exportCsv(params: Omit<AdminListParams, 'page' | 'page_size'>): Promise<Blob> {
    const resp = await api.get('/admin/uploads/export', { params, responseType: 'blob' })
    return resp.data
  },
  async syncStatus(limit = 50): Promise<{ synced: number }> {
    const resp = await api.post('/admin/uploads/sync-status', null, { params: { limit } })
    return resp.data
  },
  async overview(): Promise<{ total: number; week_count: number; failed: number; active_users_7d: number }> {
    const resp = await api.get('/admin/stats/overview')
    return resp.data
  },
  async dailyTrend(days = 30): Promise<{ items: { date: string; count: number }[] }> {
    const resp = await api.get('/admin/stats/daily-trend', { params: { days } })
    return resp.data
  },
  async topUploaders(n = 5): Promise<{ items: { user_id: string; username: string; count: number }[] }> {
    const resp = await api.get('/admin/stats/top-uploaders', { params: { n } })
    return resp.data
  },
  async kbDistribution(): Promise<{ items: { kb_id: string; kb_name: string; count: number }[] }> {
    const resp = await api.get('/admin/stats/kb-distribution')
    return resp.data
  },
}
```

- [ ] **Step 6: Write `frontend/src/stores/authStore.ts`**

```typescript
import { create } from 'zustand'
import { authApi, type UserInfo } from '@/api/auth'
import { clearToken, getToken, setToken } from '@/api/client'

interface AuthState {
  isInitialized: boolean
  isAuthenticated: boolean
  user: UserInfo | null
  initialize: () => Promise<void>
  loginWithPassword: (username: string, password: string) => Promise<void>
  loginWithToken: (token: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  isInitialized: false,
  isAuthenticated: false,
  user: null,

  initialize: async () => {
    if (!getToken()) {
      set({ isInitialized: true, isAuthenticated: false, user: null })
      return
    }
    try {
      const user = await authApi.me()
      set({ isInitialized: true, isAuthenticated: true, user })
    } catch {
      clearToken()
      set({ isInitialized: true, isAuthenticated: false, user: null })
    }
  },

  loginWithPassword: async (username, password) => {
    const data = await authApi.login(username, password)
    setToken(data.token)
    set({ isAuthenticated: true, user: data.user })
  },

  loginWithToken: (token) => {
    setToken(token)
    // 触发 initialize 拉 user 信息
    window.location.href = '/upload'
  },

  logout: () => {
    clearToken()
    set({ isAuthenticated: false, user: null })
  },
}))
```

- [ ] **Step 7: Write `frontend/src/router.tsx`**

```typescript
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

// 守卫
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isInitialized } = useAuthStore()
  if (!isInitialized) return <div className="p-8">加载中...</div>
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AdminGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()
  if (user?.role !== 'admin') return <Navigate to="/upload" replace />
  return <>{children}</>
}

// 占位组件,后续 Task 替换
function Placeholder({ name }: { name: string }) {
  return <div className="p-8">{name}</div>
}

export const router = createBrowserRouter([
  { path: '/login', element: <Placeholder name="LoginPage" /> },
  { path: '/sso', element: <Placeholder name="SsoPage" /> },
  {
    path: '/upload',
    element: <AuthGuard><Placeholder name="UploadPage" /></AuthGuard>,
  },
  {
    path: '/my-uploads',
    element: <AuthGuard><Placeholder name="MyUploadsPage" /></AuthGuard>,
  },
  {
    path: '/admin',
    element: <Navigate to="/admin/dashboard" replace />,
  },
  {
    path: '/admin/dashboard',
    element: <AuthGuard><AdminGuard><Placeholder name="AdminDashboard" /></AdminGuard></AuthGuard>,
  },
  {
    path: '/admin/uploads',
    element: <AuthGuard><AdminGuard><Placeholder name="AdminUploads" /></AdminGuard></AuthGuard>,
  },
  { path: '*', element: <Navigate to="/upload" replace /> },
])
```

- [ ] **Step 8: Modify `frontend/src/main.tsx`**

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import './index.css'
import { router } from '@/router'
import { useAuthStore } from '@/stores/authStore'

// 启动时初始化鉴权状态
useAuthStore.getState().initialize()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
```

- [ ] **Step 9: Verify route guard**

```bash
npm run dev
# 直接访问 http://localhost:3002/upload 应跳到 /login(占位页)
# 访问 /admin/dashboard 应跳到 /upload(因为没登录)
```

- [ ] **Step 10: Commit**

```bash
cd E:/github_project/RAGPortal
git add frontend/
git commit -m "feat(frontend): API client + authStore + router with guards"
```

---

### Task 13: Login page + SSO page + Layout + Navbar

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/SsoPage.tsx`
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/NavBar.tsx`
- Create: `frontend/src/components/StatusBadge.tsx`
- Create: `frontend/src/utils/format.ts`
- Modify: `frontend/src/router.tsx`

- [ ] **Step 1: Write `frontend/src/utils/format.ts`**

```typescript
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

export function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
}
```

- [ ] **Step 2: Write `frontend/src/components/StatusBadge.tsx`**

```typescript
interface Props {
  status: 'pending' | 'processing' | 'success' | 'failed'
}

const LABELS: Record<Props['status'], { text: string; cls: string; icon: string }> = {
  pending:    { text: '等待中', cls: 'bg-yellow-100 text-yellow-700', icon: '⌛' },
  processing: { text: '处理中', cls: 'bg-blue-100 text-blue-700',     icon: '⏳' },
  success:    { text: '成功',   cls: 'bg-green-100 text-green-700',   icon: '✓' },
  failed:     { text: '失败',   cls: 'bg-red-100 text-red-700',       icon: '✗' },
}

export default function StatusBadge({ status }: Props) {
  const cfg = LABELS[status]
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${cfg.cls}`}>
      <span>{cfg.icon}</span>
      {cfg.text}
    </span>
  )
}
```

- [ ] **Step 3: Write `frontend/src/pages/SsoPage.tsx`**

```typescript
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'
import { setToken } from '@/api/client'

export default function SsoPage() {
  const navigate = useNavigate()
  const loginWithToken = useAuthStore((s) => s.loginWithToken)

  useEffect(() => {
    const hash = window.location.hash || ''
    const match = hash.match(/[#&]token=([^&]+)/)
    if (!match) {
      // 无 token,显示提示并跳登录
      navigate('/login', replace: true)
      return
    }
    const token = decodeURIComponent(match[1])
    setToken(token)
    // 验证一下 token 是否真的有效
    authApi.me()
      .then(() => {
        // 清掉 hash,跳上传页
        window.history.replaceState(null, '', '/upload')
        window.location.reload()
      })
      .catch(() => {
        navigate('/login', { replace: true })
      })
  }, [navigate])

  return <div className="p-8">正在跳转...</div>
}
```

Note: there's a typo above (`navigate('/login', replace: true)` should be `navigate('/login', { replace: true })`). Correct it:

```typescript
      navigate('/login', { replace: true })
```

- [ ] **Step 4: Write `frontend/src/pages/LoginPage.tsx`**

```typescript
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'

export default function LoginPage() {
  const navigate = useNavigate()
  const loginWithPassword = useAuthStore((s) => s.loginWithPassword)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [portalUrl, setPortalUrl] = useState('')

  useState(() => {
    authApi.getConfig().then((c) => setPortalUrl(c.portal_url)).catch(() => {})
  })

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await loginWithPassword(username, password)
      navigate('/upload', { replace: true })
    } catch (err: any) {
      setError(err.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-sm border border-slate-200 p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold">
            ◆ RAG<span className="text-brand">Portal</span>
          </h1>
          <p className="text-sm text-slate-500 mt-2">AI⁴MS 知识库文档上传门户</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
              required
            />
          </div>
          {error && <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{error}</div>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 bg-brand hover:bg-brand-dark text-white font-semibold rounded-md disabled:opacity-50"
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>

        {portalUrl && (
          <div className="mt-6 text-center text-sm text-slate-500">
            没有 RAGPortal 账号?前往
            <a href={portalUrl} className="text-brand hover:underline ml-1">AI⁴MS 门户</a>
          </div>
        )}
      </div>
    </div>
  )
}
```

Note: `useState(() => { ... })` is wrong for side-effects — that's `useEffect`. Fix:

Replace `useState(() => { authApi.getConfig()... })` with `useEffect`:

```typescript
import { useEffect, useState } from 'react'
...
useEffect(() => {
  authApi.getConfig().then((c) => setPortalUrl(c.portal_url)).catch(() => {})
}, [])
```

- [ ] **Step 5: Write `frontend/src/components/NavBar.tsx`**

```typescript
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useAuthStore } from '@/stores/authStore'

export default function NavBar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [adminMenuOpen, setAdminMenuOpen] = useState(false)

  const linkCls = (path: string) =>
    `px-3 py-1.5 rounded text-sm ${
      location.pathname === path
        ? 'bg-blue-50 text-brand font-semibold'
        : 'text-slate-600 hover:text-slate-900'
    }`

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/upload" className="text-lg font-bold">
            ◆ RAG<span className="text-brand">Portal</span>
          </Link>
          <nav className="flex items-center gap-1">
            <Link to="/upload" className={linkCls('/upload')}>上传</Link>
            <Link to="/my-uploads" className={linkCls('/my-uploads')}>我的记录</Link>
            {user?.role === 'admin' && (
              <div
                className="relative"
                onMouseEnter={() => setAdminMenuOpen(true)}
                onMouseLeave={() => setAdminMenuOpen(false)}
              >
                <button className="px-3 py-1.5 rounded text-sm text-slate-600 hover:text-slate-900">
                  后台 ▾
                </button>
                {adminMenuOpen && (
                  <div className="absolute top-full left-0 bg-white border border-slate-200 rounded-md shadow-sm py-1 min-w-[140px]">
                    <Link to="/admin/dashboard" className="block px-3 py-1.5 text-sm hover:bg-slate-50">仪表盘</Link>
                    <Link to="/admin/uploads" className="block px-3 py-1.5 text-sm hover:bg-slate-50">上传记录</Link>
                  </div>
                )}
              </div>
            )}
          </nav>
        </div>

        <div
          className="relative"
          onMouseEnter={() => setUserMenuOpen(true)}
          onMouseLeave={() => setUserMenuOpen(false)}
        >
          <button className="flex items-center gap-2 px-2 py-1 rounded hover:bg-slate-100">
            <div className="w-7 h-7 rounded-full bg-brand text-white flex items-center justify-center text-xs font-semibold">
              {user?.username?.[0]?.toUpperCase() || '?'}
            </div>
            <span className="text-sm text-slate-700">{user?.username}</span>
          </button>
          {userMenuOpen && (
            <div className="absolute top-full right-0 bg-white border border-slate-200 rounded-md shadow-sm py-1 min-w-[180px]">
              <div className="px-3 py-2 border-b border-slate-100">
                <div className="text-sm font-semibold">{user?.username}</div>
                <div className="text-xs text-slate-500">{user?.organization || '—'}</div>
              </div>
              <button
                onClick={handleLogout}
                className="w-full text-left px-3 py-1.5 text-sm hover:bg-slate-50"
              >
                退出登录
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
```

- [ ] **Step 6: Write `frontend/src/components/Layout.tsx`**

```typescript
import { Outlet } from 'react-router-dom'
import NavBar from './NavBar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 7: Modify `frontend/src/router.tsx` — wire pages and use Layout**

```typescript
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import Layout from '@/components/Layout'
import LoginPage from '@/pages/LoginPage'
import SsoPage from '@/pages/SsoPage'

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isInitialized } = useAuthStore()
  if (!isInitialized) return <div className="p-8">加载中...</div>
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AdminGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()
  if (user?.role !== 'admin') return <Navigate to="/upload" replace />
  return <>{children}</>
}

function Placeholder({ name }: { name: string }) {
  return <div className="p-8 text-slate-500">{name} — 待实现</div>
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/sso', element: <SsoPage /> },
  {
    element: <Layout />,
    children: [
      {
        path: '/upload',
        element: <AuthGuard><Placeholder name="UploadPage" /></AuthGuard>,
      },
      {
        path: '/my-uploads',
        element: <AuthGuard><Placeholder name="MyUploadsPage" /></AuthGuard>,
      },
      {
        path: '/admin',
        element: <Navigate to="/admin/dashboard" replace />,
      },
      {
        path: '/admin/dashboard',
        element: <AuthGuard><AdminGuard><Placeholder name="AdminDashboard" /></AdminGuard></AuthGuard>,
      },
      {
        path: '/admin/uploads',
        element: <AuthGuard><AdminGuard><Placeholder name="AdminUploads" /></AdminGuard></AuthGuard>,
      },
      { path: '*', element: <Navigate to="/upload" replace /> },
    ],
  },
])
```

- [ ] **Step 8: Manual verification**

```bash
npm run dev
# 1) 访问 /login 应看到登录页
# 2) 访问 /upload(未登录)应跳 /login
# 3) 通过 SSO 链接(http://localhost:3002/sso#token=<valid_token>)应跳到 /upload
# 4) 用 admin token 进 /upload,应看到顶部导航有"后台 ▾"
```

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): Login + SSO pages + Layout + NavBar"
```

---

## Phase 6: Frontend Core

### Task 14: Upload page (drag/drop, multi-file, folder)

**Files:**
- Create: `frontend/src/components/KbSelector.tsx`
- Create: `frontend/src/components/UploadDropzone.tsx`
- Create: `frontend/src/stores/uploadStore.ts`
- Create: `frontend/src/pages/UploadPage.tsx`
- Create: `frontend/src/utils/fileFilter.ts`
- Modify: `frontend/src/router.tsx` (use UploadPage)

- [ ] **Step 1: Write `frontend/src/utils/fileFilter.ts`**

```typescript
const HIDDEN_PATTERNS = [
  /\.DS_Store$/i,
  /^Thumbs\.db$/i,
  /^__MACOSX\//i,
  /\.git\//i,
  /^node_modules\//i,
  /^\./, // 隐藏文件(开头是点)
]

export function isHiddenFile(relativePath: string): boolean {
  return HIDDEN_PATTERNS.some((p) => p.test(relativePath))
}

export function filterValidFiles(files: File[]): File[] {
  return files.filter((f) => {
    const path = (f as any).webkitRelativePath || f.name
    return !isHiddenFile(path)
  })
}
```

- [ ] **Step 2: Write `frontend/src/components/KbSelector.tsx`**

```typescript
import { useEffect, useState } from 'react'
import { kbApi, type KbInfo } from '@/api/kb'

interface Props {
  value: string
  onChange: (id: string) => void
}

export default function KbSelector({ value, onChange }: Props) {
  const [kbs, setKbs] = useState<KbInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    kbApi.list().then(setKbs).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-sm text-slate-500">加载知识库...</div>

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-3 py-2 border border-slate-300 rounded-md bg-white min-w-[240px]"
    >
      <option value="">请选择知识库</option>
      {kbs.map((kb) => (
        <option key={kb.id} value={kb.id}>{kb.name}</option>
      ))}
    </select>
  )
}
```

- [ ] **Step 3: Write `frontend/src/stores/uploadStore.ts`**

```typescript
import { create } from 'zustand'
import { uploadsApi } from '@/api/uploads'
import { filterValidFiles } from '@/utils/fileFilter'

export type UploadItemStatus = 'pending' | 'uploading' | 'success' | 'failed'

export interface UploadItem {
  id: string
  file: File
  progress: number
  status: UploadItemStatus
  error: string
  result?: any
}

interface UploadState {
  items: UploadItem[]
  concurrency: number
  addFiles: (files: File[], kbId: string) => void
  clearCompleted: () => void
}

const MAX_CONCURRENCY = 5

export const useUploadStore = create<UploadState>((set, get) => ({
  items: [],
  concurrency: MAX_CONCURRENCY,

  addFiles: (files, kbId) => {
    const valid = filterValidFiles(Array.from(files))
    const newItems: UploadItem[] = valid.map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      file,
      progress: 0,
      status: 'pending',
      error: '',
    }))
    set({ items: [...get().items, ...newItems] })
    // 限制并发,启动上传
    get().items
      .filter((it) => it.status === 'pending')
      .slice(0, MAX_CONCURRENCY)
      .forEach((it) => startUpload(it.id, kbId, set, get))
  },

  clearCompleted: () => {
    set({ items: get().items.filter((it) => it.status !== 'success' && it.status !== 'failed') })
  },
}))

async function startUpload(id: string, kbId: string, set: any, get: any) {
  const update = (patch: Partial<UploadItem>) =>
    set({ items: get().items.map((it) => (it.id === id ? { ...it, ...patch } : it)) })

  update({ status: 'uploading', progress: 0 })

  const item = get().items.find((it: UploadItem) => it.id === id)
  if (!item) return

  try {
    const result = await uploadsApi.upload(item.file, kbId, (pct) => update({ progress: pct }))
    update({ status: 'success', progress: 100, result })
  } catch (err: any) {
    const msg = err.response?.data?.detail || err.message || '上传失败'
    update({ status: 'failed', error: msg })
  }

  // 启动队列中下一条
  const next = get().items.find((it: UploadItem) => it.status === 'pending')
  if (next) startUpload(next.id, kbId, set, get)
}
```

- [ ] **Step 4: Write `frontend/src/components/UploadDropzone.tsx`**

```typescript
import { useDropzone } from 'react-dropzone'
import { Upload } from 'lucide-react'

interface Props {
  onFiles: (files: File[]) => void
  maxSizeMb: number
  allowedTypes: string[]
}

export default function UploadDropzone({ onFiles, maxSizeMb, allowedTypes }: Props) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (accepted) => onFiles(accepted),
    // weknora 后端会做严格校验,这里不做 reject,只做提示
  })

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors
        ${isDragActive ? 'border-brand bg-blue-50' : 'border-slate-300 bg-white hover:border-brand'}`}
    >
      <input {...getInputProps()} />
      <Upload className="mx-auto mb-3 text-brand" size={32} />
      <div className="text-base font-semibold text-slate-900 mb-1">
        拖拽文件或文件夹到此处
      </div>
      <div className="text-xs text-slate-500 mb-4">
        支持 {allowedTypes.join(' / ')},单个文件 ≤ {maxSizeMb}MB
      </div>
      <div className="flex gap-2 justify-center text-sm">
        <span className="px-3 py-1.5 bg-brand text-white rounded-md">选择文件</span>
      </div>
      {/* 文件夹选择(单独的 input,因为 react-dropzone 不直接支持) */}
      <label className="block mt-2 text-xs text-slate-500 cursor-pointer hover:underline">
        <input
          type="file"
          multiple
          // @ts-ignore webkitdirectory 是非标准属性
          webkitdirectory=""
          directory=""
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files || [])
            if (files.length) onFiles(files)
            e.currentTarget.value = ''
          }}
        />
        <span>或 选择整个文件夹</span>
      </label>
    </div>
  )
}
```

Note: requires `lucide-react` icon package. Install:

```bash
cd frontend
npm install lucide-react
```

- [ ] **Step 5: Write `frontend/src/pages/UploadPage.tsx`**

```typescript
import { useEffect, useState } from 'react'
import KbSelector from '@/components/KbSelector'
import UploadDropzone from '@/components/UploadDropzone'
import StatusBadge from '@/components/StatusBadge'
import { useUploadStore } from '@/stores/uploadStore'
import { authApi } from '@/api/auth'
import { formatFileSize } from '@/utils/format'

export default function UploadPage() {
  const [kbId, setKbId] = useState('')
  const [config, setConfig] = useState<{ max_size_mb: number; allowed_file_types: string[] } | null>(null)
  const { items, addFiles, clearCompleted } = useUploadStore()

  useEffect(() => {
    authApi.getConfig().then((c) => setConfig({ max_size_mb: c.max_size_mb, allowed_file_types: c.allowed_file_types }))
  }, [])

  const completed = items.filter((it) => it.status === 'success' || it.status === 'failed').length
  const totalProgress = items.length ? Math.round((completed / items.length) * 100) : 0

  function handleFiles(files: File[]) {
    if (!kbId) {
      alert('请先选择知识库')
      return
    }
    addFiles(files, kbId)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-600">上传到:</span>
        <KbSelector value={kbId} onChange={setKbId} />
      </div>

      {config && (
        <UploadDropzone
          onFiles={handleFiles}
          maxSizeMb={config.max_size_mb}
          allowedTypes={config.allowed_file_types}
        />
      )}

      {items.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">
              本次上传 ({completed} / {items.length} 完成)
            </h3>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500">总进度 {totalProgress}%</span>
              <button onClick={clearCompleted} className="text-xs text-slate-500 hover:underline">
                清空已完成
              </button>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-lg divide-y divide-slate-100">
            {items.map((it) => (
              <div key={it.id} className="grid grid-cols-[20px_1fr_80px_100px] gap-3 items-center px-4 py-2.5">
                <span className="text-sm">
                  {it.status === 'success' && <span className="text-green-600">✓</span>}
                  {it.status === 'failed' && <span className="text-red-600">✗</span>}
                  {(it.status === 'pending' || it.status === 'uploading') && (
                    <span className="text-blue-600">⏳</span>
                  )}
                </span>
                <div className="min-w-0">
                  <div className="text-sm text-slate-900 truncate">
                    {(it.file as any).webkitRelativePath || it.file.name}
                  </div>
                  {it.status === 'uploading' && (
                    <div className="mt-1 h-1 bg-slate-100 rounded overflow-hidden">
                      <div className="h-full bg-brand transition-all" style={{ width: `${it.progress}%` }} />
                    </div>
                  )}
                  {it.status === 'failed' && (
                    <div className="text-xs text-red-600 mt-0.5">{it.error}</div>
                  )}
                </div>
                <span className="text-xs text-slate-500 text-right">{formatFileSize(it.file.size)}</span>
                <div className="text-right">
                  <StatusBadgeForItem status={it.status} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatusBadgeForItem({ status }: { status: string }) {
  if (status === 'success') return <span className="text-xs px-2 py-0.5 rounded bg-green-100 text-green-700 font-semibold">成功</span>
  if (status === 'failed') return <span className="text-xs px-2 py-0.5 rounded bg-red-100 text-red-700 font-semibold">失败</span>
  if (status === 'uploading') return <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700 font-semibold">上传中</span>
  return <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-semibold">等待中</span>
}
```

- [ ] **Step 6: Modify `frontend/src/router.tsx` — replace UploadPage placeholder**

Replace `<Placeholder name="UploadPage" />` with `<UploadPage />` and import it:

```typescript
import UploadPage from '@/pages/UploadPage'
...
{
  path: '/upload',
  element: <AuthGuard><UploadPage /></AuthGuard>,
},
```

- [ ] **Step 7: Manual verification**

```bash
npm run dev
# 登录后:
# 1) 选择一个 KB
# 2) 拖拽单个文件 → 应开始上传,显示进度条 → 完成
# 3) 点击"选择整个文件夹" → 应批量上传(过滤隐藏文件)
# 4) 上传不支持的类型(如 .mp4) → 应该报"文件类型不允许"
# 5) 后端 SQLite 中应有对应记录,WeKnora 中 knowledge.metadata 含 uploader 信息
```

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): upload page with drag/drop + multi-file + folder support"
```

---

### Task 15: My Uploads page

**Files:**
- Create: `frontend/src/pages/MyUploadsPage.tsx`
- Create: `frontend/src/components/Pagination.tsx`
- Modify: `frontend/src/router.tsx`

- [ ] **Step 1: Write `frontend/src/components/Pagination.tsx`**

```typescript
interface Props {
  page: number
  pageSize: number
  total: number | undefined
  onChange: (page: number) => void
}

export default function Pagination({ page, pageSize, total, onChange }: Props) {
  const totalPages = total ? Math.ceil(total / pageSize) : 1
  if (totalPages <= 1) return null
  return (
    <div className="flex justify-between items-center pt-3 text-xs text-slate-500">
      <span>共 {total ?? '--'} 条</span>
      <div className="flex gap-1">
        <button
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="px-2 py-1 border border-slate-300 rounded bg-white disabled:opacity-50"
        >
          ‹
        </button>
        <span className="px-3 py-1">{page} / {totalPages}</span>
        <button
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
          className="px-2 py-1 border border-slate-300 rounded bg-white disabled:opacity-50"
        >
          ›
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Write `frontend/src/pages/MyUploadsPage.tsx`**

```typescript
import { useEffect, useState } from 'react'
import { uploadsApi, type UploadRecord } from '@/api/uploads'
import StatusBadge from '@/components/StatusBadge'
import Pagination from '@/components/Pagination'
import { formatFileSize, formatTime } from '@/utils/format'

const PAGE_SIZE = 20

export default function MyUploadsPage() {
  const [items, setItems] = useState<UploadRecord[]>([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    uploadsApi.mine(page, PAGE_SIZE).then((data) => setItems(data.items)).finally(() => setLoading(false))
  }, [page])

  return (
    <div>
      <h2 className="text-lg font-bold mb-4">我的上传记录</h2>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="grid grid-cols-[2fr_1.5fr_0.8fr_0.9fr_1.2fr] gap-3 px-4 py-2.5 bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
          <div>文件名</div>
          <div>知识库</div>
          <div className="text-right">大小</div>
          <div className="text-center">状态</div>
          <div className="text-right">上传时间</div>
        </div>
        {loading ? (
          <div className="px-4 py-12 text-center text-slate-500">加载中...</div>
        ) : items.length === 0 ? (
          <div className="px-4 py-12 text-center text-slate-500">还没有上传记录</div>
        ) : (
          items.map((u) => (
            <div key={u.id} className="grid grid-cols-[2fr_1.5fr_0.8fr_0.9fr_1.2fr] gap-3 px-4 py-3 border-t border-slate-100 text-sm">
              <div className="truncate" title={u.file_name}>{u.file_name}</div>
              <div className="truncate text-slate-600">{u.kb_name}</div>
              <div className="text-right text-slate-500">{formatFileSize(u.file_size)}</div>
              <div className="text-center">
                <StatusBadge status={u.parse_status} />
                {u.parse_status === 'failed' && u.parse_error && (
                  <div className="text-xs text-red-600 mt-1 truncate" title={u.parse_error}>{u.parse_error}</div>
                )}
              </div>
              <div className="text-right text-slate-500">{formatTime(u.uploaded_at)}</div>
            </div>
          ))
        )}
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} onChange={setPage} />
    </div>
  )
}
```

- [ ] **Step 3: Modify `frontend/src/router.tsx` — replace MyUploadsPage placeholder**

```typescript
import MyUploadsPage from '@/pages/MyUploadsPage'
...
{
  path: '/my-uploads',
  element: <AuthGuard><MyUploadsPage /></AuthGuard>,
},
```

- [ ] **Step 4: Manual verification**

```bash
npm run dev
# 登录后访问 /my-uploads,应看到自己上传过的记录(若 SQLite 里有数据)
```

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): my-uploads page with pagination"
```

---

## Phase 7: Admin Frontend

### Task 16: Admin dashboard (charts)

**Files:**
- Create: `frontend/src/pages/admin/DashboardPage.tsx`
- Modify: `frontend/src/router.tsx`

- [ ] **Step 1: Write `frontend/src/pages/admin/DashboardPage.tsx`**

```typescript
import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, XAxis as BarX, Cell,
  PieChart, Pie, Cell as PieCell, Legend,
} from 'recharts'
import { adminApi } from '@/api/admin'

interface Overview { total: number; week_count: number; failed: number; active_users_7d: number }
interface TrendItem { date: string; count: number }
interface TopItem { user_id: string; username: string; count: number }
interface KbItem { kb_id: string; kb_name: string; count: number }

const PIE_COLORS = ['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe']

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [trend, setTrend] = useState<TrendItem[]>([])
  const [top, setTop] = useState<TopItem[]>([])
  const [kbs, setKbs] = useState<KbItem[]>([])

  useEffect(() => {
    Promise.all([
      adminApi.overview(),
      adminApi.dailyTrend(30),
      adminApi.topUploaders(5),
      adminApi.kbDistribution(),
    ]).then(([o, t, tp, k]) => {
      setOverview(o)
      setTrend(t.items)
      setTop(tp.items)
      setKbs(k.items)
    })
  }, [])

  if (!overview) return <div className="p-8">加载中...</div>

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">数据概览</h2>

      {/* KPI 卡 */}
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="总上传数" value={overview.total} />
        <KpiCard label="本周上传" value={overview.week_count} />
        <KpiCard label="解析失败" value={overview.failed} valueClass="text-red-600" />
        <KpiCard label="活跃用户 (7天)" value={overview.active_users_7d} />
      </div>

      {/* 趋势 + Top */}
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2 bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-2">每日上传量趋势(近 30 天)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-2">上传者 Top 5</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={top}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <BarX dataKey="username" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* KB 分布 */}
      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold mb-2">各知识库上传分布</h3>
        <ResponsiveContainer width="100%" height={240}>
          <PieChart>
            <Pie data={kbs} dataKey="count" nameKey="kb_name" cx="50%" cy="50%" outerRadius={80} label>
              {kbs.map((_, i) => <PieCell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
            </Pie>
            <Legend />
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function KpiCard({ label, value, valueClass = '' }: { label: string; value: number; valueClass?: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-2xl font-bold ${valueClass}`}>{value.toLocaleString()}</div>
    </div>
  )
}
```

Note: imports `XAxis as BarX` and unused `Cell` / `Cell as PieCell` — clean them up: remove the unused `Cell` import. Use just `XAxis` for the bar chart; alias not needed if we restructure imports. Final imports should be:

```typescript
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar,
  PieChart, Pie, Cell as PieCell, Legend,
} from 'recharts'
```

(Use `XAxis` directly in both charts; remove `BarX`/`Cell`.)

- [ ] **Step 2: Modify `frontend/src/router.tsx` — replace Dashboard placeholder**

```typescript
import DashboardPage from '@/pages/admin/DashboardPage'
...
{
  path: '/admin/dashboard',
  element: <AuthGuard><AdminGuard><DashboardPage /></AdminGuard></AuthGuard>,
},
```

- [ ] **Step 3: Manual verification**

```bash
npm run dev
# 用 admin 账号登录,访问 /admin/dashboard,应看到 KPI 卡 + 趋势图 + Top 5 + KB 分布饼图
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): admin dashboard with KPIs and charts"
```

---

### Task 17: Admin uploads list (filter + CSV export)

**Files:**
- Create: `frontend/src/pages/admin/UploadsAdminPage.tsx`
- Modify: `frontend/src/router.tsx`

- [ ] **Step 1: Write `frontend/src/pages/admin/UploadsAdminPage.tsx`**

```typescript
import { useEffect, useState } from 'react'
import { adminApi, type AdminListParams } from '@/api/admin'
import { kbApi, type KbInfo } from '@/api/kb'
import type { UploadRecord } from '@/api/uploads'
import StatusBadge from '@/components/StatusBadge'
import Pagination from '@/components/Pagination'
import { formatFileSize, formatTime } from '@/utils/format'

const PAGE_SIZE = 20

export default function UploadsAdminPage() {
  const [items, setItems] = useState<UploadRecord[]>([])
  const [total, setTotal] = useState(0)
  const [kbs, setKbs] = useState<KbInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<AdminListParams>({
    page: 1,
    page_size: PAGE_SIZE,
    uploader: '',
    kb_id: '',
    status: '',
    filename: '',
    start: '',
    end: '',
  })

  useEffect(() => {
    kbApi.list().then(setKbs).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    adminApi.list(filters).then((data) => {
      setItems(data.items)
      setTotal(data.total)
    }).finally(() => setLoading(false))
  }, [filters])

  function update<K extends keyof AdminListParams>(key: K, value: AdminListParams[K]) {
    setFilters({ ...filters, [key]: value, page: 1 })
  }

  async function handleExport() {
    const blob = await adminApi.exportCsv(filters)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `uploads_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function handleSync() {
    const r = await adminApi.syncStatus(50)
    alert(`已同步 ${r.synced} 条记录`)
    setFilters({ ...filters }) // 触发刷新
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">全部上传记录</h2>
        <button onClick={handleSync} className="text-sm text-slate-600 hover:text-slate-900 px-3 py-1.5 border border-slate-300 rounded bg-white">
          ↻ 刷新状态
        </button>
      </div>

      {/* 筛选条 */}
      <div className="bg-white border border-slate-200 rounded-lg p-3 grid grid-cols-6 gap-2 text-xs">
        <input
          placeholder="上传者"
          value={filters.uploader || ''}
          onChange={(e) => update('uploader', e.target.value)}
          className="border border-slate-300 rounded px-2 py-1"
        />
        <select
          value={filters.kb_id || ''}
          onChange={(e) => update('kb_id', e.target.value)}
          className="border border-slate-300 rounded px-2 py-1 bg-white"
        >
          <option value="">全部 KB</option>
          {kbs.map((kb) => <option key={kb.id} value={kb.id}>{kb.name}</option>)}
        </select>
        <select
          value={filters.status || ''}
          onChange={(e) => update('status', e.target.value)}
          className="border border-slate-300 rounded px-2 py-1 bg-white"
        >
          <option value="">全部状态</option>
          <option value="pending">等待中</option>
          <option value="processing">处理中</option>
          <option value="success">成功</option>
          <option value="failed">失败</option>
        </select>
        <input type="date" value={filters.start || ''} onChange={(e) => update('start', e.target.value)} className="border border-slate-300 rounded px-2 py-1" />
        <input type="date" value={filters.end || ''} onChange={(e) => update('end', e.target.value)} className="border border-slate-300 rounded px-2 py-1" />
        <input
          placeholder="文件名"
          value={filters.filename || ''}
          onChange={(e) => update('filename', e.target.value)}
          className="border border-slate-300 rounded px-2 py-1"
        />
      </div>

      <div className="flex justify-end">
        <button onClick={handleExport} className="bg-brand hover:bg-brand-dark text-white text-sm font-semibold px-4 py-2 rounded">
          ⬇ 导出 CSV
        </button>
      </div>

      {/* 表格 */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="grid grid-cols-[1.2fr_1.5fr_1.2fr_0.7fr_0.8fr_1fr] gap-3 px-4 py-2.5 bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
          <div>上传者</div>
          <div>文件名</div>
          <div>知识库</div>
          <div className="text-right">大小</div>
          <div className="text-center">状态</div>
          <div className="text-right">上传时间</div>
        </div>
        {loading ? (
          <div className="px-4 py-12 text-center text-slate-500">加载中...</div>
        ) : items.length === 0 ? (
          <div className="px-4 py-12 text-center text-slate-500">没有符合条件的记录</div>
        ) : (
          items.map((u) => (
            <div key={u.id} className="grid grid-cols-[1.2fr_1.5fr_1.2fr_0.7fr_0.8fr_1fr] gap-3 px-4 py-3 border-t border-slate-100 text-sm">
              <div>
                <div className="font-semibold text-slate-900">{u.uploader_username}</div>
                <div className="text-xs text-slate-500">{u.uploader_organization || '—'}</div>
              </div>
              <div className="truncate" title={u.file_name}>{u.file_name}</div>
              <div className="truncate text-slate-600">{u.kb_name}</div>
              <div className="text-right text-slate-500">{formatFileSize(u.file_size)}</div>
              <div className="text-center">
                <StatusBadge status={u.parse_status} />
                {u.parse_status === 'failed' && u.parse_error && (
                  <div className="text-xs text-red-600 mt-1 truncate" title={u.parse_error}>{u.parse_error}</div>
                )}
              </div>
              <div className="text-right text-slate-500">{formatTime(u.uploaded_at)}</div>
            </div>
          ))
        )}
      </div>

      <Pagination
        page={filters.page || 1}
        pageSize={PAGE_SIZE}
        total={total}
        onChange={(p) => setFilters({ ...filters, page: p })}
      />
    </div>
  )
}
```

- [ ] **Step 2: Modify `frontend/src/router.tsx` — replace UploadsAdmin placeholder**

```typescript
import UploadsAdminPage from '@/pages/admin/UploadsAdminPage'
...
{
  path: '/admin/uploads',
  element: <AuthGuard><AdminGuard><UploadsAdminPage /></AdminGuard></AuthGuard>,
},
```

- [ ] **Step 3: Manual verification**

```bash
npm run dev
# admin 登录后访问 /admin/uploads:
# 1) 应看到全部记录,带筛选条
# 2) 选个 KB 过滤,表格应刷新
# 3) 点"导出 CSV"应下载文件,Excel 打开中文正常
# 4) 点"刷新状态"应触发懒同步,alert 显示同步条数
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): admin uploads list with filter + CSV export"
```

---

## Phase 8: Deployment

### Task 18: pm2 ecosystem + README + final integration test

**Files:**
- Create: `ecosystem.config.cjs`
- Modify: `README.md` (final deployment section)

- [ ] **Step 1: Build frontend**

```bash
cd E:/github_project/RAGPortal/frontend
npm run build
# 产物:frontend/dist/
```

- [ ] **Step 2: Configure FastAPI to serve static frontend in production**

Modify `backend/app/main.py` — add at the end (after `health`):

```python
import os
from fastapi.staticfiles import StaticFiles

# 生产环境:挂载前端静态文件
frontend_dist = os.environ.get("FRONTEND_DIST", "../frontend/dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
```

This must come AFTER all API routes are registered, since `mount("/", ...)` catches everything.

- [ ] **Step 3: Write `ecosystem.config.cjs` at project root**

```javascript
module.exports = {
  apps: [
    {
      name: 'ragportal-backend',
      script: 'backend/venv/Scripts/uvicorn',
      args: 'app.main:app --host 127.0.0.1 --port 8002',
      cwd: __dirname,
      env: { APP_ENV: 'production', PYTHONUNBUFFERED: '1' },
      instances: 1,
      autorestart: true,
    },
  ],
}
```

- [ ] **Step 4: Update `README.md` with deployment section**

Append:

```markdown
## 部署(pm2)

```bash
# 一次性准备
cd backend && python -m venv venv && source venv/Scripts/activate && pip install -r requirements.txt && cd ..
cd frontend && npm install && npm run build && cd ..
cp .env.example .env  # 修改其中的密钥与域名

# 启动
pm2 start ecosystem.config.cjs
pm2 save
```

## Nginx 反向代理(示例)

```nginx
server {
    listen 80;
    server_name rag.wumiaox.com;
    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 100M;
    }
}
```
```

- [ ] **Step 5: Final integration smoke test**

```bash
# 启动后端(生产模式)
cd backend
source venv/Scripts/activate
APP_ENV=production FRONTEND_DIST=../frontend/dist uvicorn app.main:app --port 8002

# 浏览器访问 http://localhost:8002/ 应该看到登录页(前端 SPA)
# /api/health 应返回 {"status":"ok"}
# /api/config 应返回 JSON
```

- [ ] **Step 6: Final commit**

```bash
cd E:/github_project/RAGPortal
git add .
git commit -m "chore: pm2 deployment config + README deployment section"
```

---

## Self-Review Checklist

Spec coverage (cross-checked against `2026-07-31-ragportal-design.md`):

| Spec section | Plan task(s) | Status |
|--------------|--------------|--------|
| §3 认证 (HMAC, SSO 双路径) | Task 4, 5, 13 | ✓ |
| §4 上传链路 (BFF, metadata 注入, 文件夹, 并发, 错误矩阵) | Task 7, 9, 14 | ✓ |
| §4 解析状态懒同步 | Task 8, 10 (sync-status endpoint) | ✓ |
| §5 数据模型 (uploads 表 + 索引) | Task 3 | ✓ |
| §6 前端页面结构 | Task 13–17 | ✓ |
| §7 视觉风格 B | Task 11 (Tailwind 配色) | ✓ |
| §8 后端 API | Task 5, 9, 10 | ✓ |
| §9 技术栈 | Task 1, 11 | ✓ |
| §10 项目结构 | Task 1 (matches) | ✓ |
| §11 配置项 | Task 1 (.env.example) | ✓ |
| §12 AI4MS 接入(可选) | Not implemented (user opted out) | N/A |
| §13 测试策略 | Task 4, 6, 7, 8 (core only) | ✓ |
| §14 部署 | Task 18 | ✓ |

Type consistency: `UserInfo` defined in Task 5 (auth.py) → reused in Task 9 (uploads.py) and Task 10 (admin.py). `UploadRecord` TS type defined in Task 12 → reused in Tasks 14–17. `WeknoraError` raised in Task 7 → caught in Task 9.

All steps are bite-sized, have exact paths, exact commands, and complete code. Ready to execute.
