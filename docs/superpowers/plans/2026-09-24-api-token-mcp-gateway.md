# RAGPortal API Token 与 MCP 网关第一版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为每个 RAGPortal 账户提供可勾选权限的 API Token，并通过 `/api/mcp` 为 WorkBuddy/SKILL 提供受控的远程 MCP 访问。

**Architecture:** AI4MS HMAC 登录继续负责浏览器会话；RAGPortal 新增账户级 Token 表，Token 只保存 SHA-256 摘要。MCP HTTP 路由统一验证 Bearer Token、检查 Tool 权限，再调用已有 SQLAlchemy/WeKnora 服务；WeKnora API Key 永不下发客户端。

**Tech Stack:** FastAPI、SQLAlchemy async、SQLite、React、TypeScript、WeKnora HTTP API。

**Spec:** `docs/specs/2026-09-24-pi-private-knowledge-space-prd.md` 及本轮确认的账户级 API Token 设计。

## Global Constraints

- 所有用户可见文档与界面文案使用中文。
- Token 明文仅在创建响应中返回一次，数据库只保存摘要。
- 默认 Token 权限为只读；写入权限必须显式勾选。
- MCP 请求只能经 RAGPortal，禁止暴露 WeKnora API Key、数据库和 AI4MS 密码。
- 新函数使用中文功能注释及参数注释，Python 遵循 PEP8。
- 不引入新微服务、Redis、Celery 或新向量数据库。

## Review Focus

- Token 明文不落库且撤销后立即失效：Token 服务测试。
- 缺少 Tool 权限时返回 403：MCP 路由测试。
- MCP 请求不能绕过空间/用户边界：文档列表只返回当前 Token 用户的上传记录。
- 非法 JSON-RPC/MCP 方法返回可诊断错误：MCP 协议测试。
- 前端构建必须通过 TypeScript 严格检查：前端 build。

### Task 1: Token 数据模型与服务

**Files:**
- Create: `backend/app/models/api_token.py`
- Create: `backend/app/services/api_token_service.py`
- Create: `backend/app/api/v1/api_tokens.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/core/db.py`, `backend/app/main.py`
- Test: `backend/app/tests/test_api_tokens.py`

实现 Token 创建、列表、撤销、删除和 Bearer 解析；权限字段使用 JSON 字符串保存，支持 `documents:list/search/read/download/write/update`。

### Task 2: MCP 网关与 WeKnora 代理

**Files:**
- Create: `backend/app/api/mcp.py`
- Create: `backend/app/services/mcp_service.py`
- Modify: `backend/app/core/weknora.py`, `backend/app/core/config.py`, `backend/app/main.py`
- Test: `backend/app/tests/test_mcp.py`

实现 Streamable HTTP 风格 JSON-RPC：`initialize`、`tools/list`、`tools/call`。第一版 Tool 为 `rag_list_documents`、`rag_search`、`rag_get_document`、`rag_download_file`、`rag_upload_document`。所有 Tool 先验证 Token 权限，再访问 Upload 数据或 WeKnora。

### Task 3: Token 管理前端与接入说明

**Files:**
- Create: `frontend/src/api/apiTokens.ts`
- Create: `frontend/src/pages/ApiTokensPage.tsx`
- Modify: `frontend/src/router.tsx`, `frontend/src/components/NavBar.tsx`
- Modify: `README.md`

增加账户管理页、权限复选框、一次性明文展示、撤销操作和 MCP 配置示例。

### Task 4: 全量验证

- Run: `cd backend; python -m pytest -q`
- Run: `cd frontend; npm run build`
- Verify: API 文档包含 `/api/mcp` 与 `/api/api-tokens`，前端路由可构建。
