# 知识库申请审批 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 普通用户提交知识库申请，管理员审批后由系统按默认模板创建 WeKnora 知识库并回填可上传的 `kb_id`。

**Architecture:** 新增一张本地申请表保存申请、审批与创建状态。后端提供用户提交接口和管理员审核接口，审核通过时由服务层调用 WeKnora 创建知识库。前端在上传页增加申请入口，在管理端增加申请审核页面，知识库选择仍复用现有列表接口。

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, React, TypeScript, WeKnora API

---

### Task 1: 增加知识库申请数据模型和迁移

**Files:**
- Create: `backend/app/models/kb_request.py`
- Modify: `backend/app/core/db.py`
- Modify: `backend/app/models/__init__.py` if存在导出聚合

- [ ] **Step 1: 设计申请记录字段**

`KbRequest` 需要包含：`id`、`requester_user_id`、`requester_username`、`requester_organization`、`requested_name`、`requested_description`、`request_reason`、`status`、`reviewer_user_id`、`reviewer_username`、`review_reason`、`approved_kb_id`、`approved_kb_name`、`create_error`、`created_at`、`updated_at`。

- [ ] **Step 2: 接入建表与历史列迁移**

在 `init_db()` 里把新模型纳入 `create_all`，并为 SQLite 历史库补齐必要列和索引。

- [ ] **Step 3: 验证模型导入**

Run: `C:\\conda_envs\\ragportal\\python.exe -m compileall app`
Expected: 通过，无导入错误。

### Task 2: 封装 WeKnora 创建知识库客户端

**Files:**
- Modify: `backend/app/core/weknora.py`
- Create: `backend/app/services/kb_create_service.py`

- [ ] **Step 1: 写创建接口封装**

为 `POST /api/v1/knowledge-bases` 增加一个异步封装，传入 `name`、`description` 和后端默认模板。

- [ ] **Step 2: 固定默认模板**

默认值固定在后端服务层，不从前端透出模型选择。模板里显式设置 `type=document`、`is_temporary=false`，其余配置按系统默认值补齐。

- [ ] **Step 3: 验证响应结构**

Run: `C:\\conda_envs\\ragportal\\python.exe -m pytest app\\tests\\test_weknora_*.py`
Expected: 现有 WeKnora 客户端测试继续通过。

### Task 3: 实现申请提交与管理员审批接口

**Files:**
- Create: `backend/app/services/kb_request_service.py`
- Create: `backend/app/api/v1/kb_requests.py`
- Create: `backend/app/api/v1/admin_kb_requests.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 实现用户提交**

普通用户通过 `/api/kb-requests` 提交申请，只能填写名称、描述和理由。

- [ ] **Step 2: 实现管理员审批**

管理员通过 `/api/admin/kb-requests/:id/approve` 触发创建知识库；通过 `/reject` 驳回申请。

- [ ] **Step 3: 处理失败状态**

若 WeKnora 创建失败，把申请改为 `failed` 并保留错误信息，避免卡在处理中。

- [ ] **Step 4: 接入 FastAPI 路由**

在 `main.py` 注册新路由，保持现有认证与权限风格一致。

### Task 4: 前端增加申请入口与审核页面

**Files:**
- Modify: `frontend/src/pages/UploadPage.tsx`
- Create: `frontend/src/pages/admin/KbRequestsPage.tsx`
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/api/admin.ts`
- Create: `frontend/src/api/kbRequests.ts`

- [ ] **Step 1: 上传页增加申请入口**

在知识库下拉框旁增加“申请新知识库”按钮，弹出轻量表单。

- [ ] **Step 2: 管理员页面展示申请列表**

管理员可看到待审核、已通过、已驳回的申请，并执行通过/拒绝。

- [ ] **Step 3: 申请通过后刷新知识库列表**

审批成功后刷新知识库下拉框数据，确保新库立刻可选。

### Task 5: 补测试并做端到端验证

**Files:**
- Create: `backend/app/tests/test_kb_request_service.py`
- Create: `backend/app/tests/test_kb_requests_api.py`
- Create: `frontend/src/pages/__tests__/...` only if必要

- [ ] **Step 1: 测试申请状态流转**

覆盖提交、通过、拒绝、WeKnora 创建失败这几条主路径。

- [ ] **Step 2: 验证现有上传流程不受影响**

Run: `C:\\conda_envs\\ragportal\\python.exe -m pytest app\\tests\\test_backfill_service.py app\\tests\\test_uploads_mine_sync.py app\\tests\\test_sync_service.py`
Expected: 通过。

- [ ] **Step 3: 验证前端构建**

Run: `npm run build`
Expected: 构建通过。

