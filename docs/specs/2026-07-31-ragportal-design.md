# RAGPortal 设计文档

| 项目 | 内容 |
|------|------|
| 文档日期 | 2026-07-31 |
| 项目名称 | RAGPortal |
| 项目路径 | `E:\github_project\RAGPortal`(待创建) |
| 部署形态 | 独立子域名(如 `rag.xmuzc.com`) |
| 上游依赖 | AI4MS 门户(认证源)、WeKnora(文档存储与解析) |
| 是否改动 WeKnora | **否** |
| 是否改动 AI4MS | **否**(`HomePage` 卡片配置追加是可选项,由用户自行决定) |

## 1. 项目目标

构建一个独立的"知识库文档上传"前端应用,作为 AI⁴MS 门户的子应用,基于 AI⁴MS 账号登录,向 WeKnora 指定 API Key 范围内的知识库上传文档,并记录每个文档的上传者,便于后台查询、统计、导出。

### 核心功能边界

1. **登录**:复用 AI4MS HMAC Token,支持门户 SSO 跳转 + 独立登录页双路径
2. **文档上传**:支持单文件、多文件、文件夹上传;支持选择目标 KB
3. **个人历史**:普通用户可查看自己上传历史及解析状态
4. **admin 后台**:统计仪表盘 + 上传记录筛选/搜索/CSV 导出
5. **不包含**:文档在线编辑、删除文档、知识库管理、向量化参数调优、用户管理

## 2. 整体架构

```
┌──────────────────┐   SSO 跳转 (#token=xxx)   ┌─────────────────────────────┐
│  AI4MS 门户       │ ─────────────────────→   │  RAGPortal (新建独立应用)    │
│  React + FastAPI  │                          │                              │
│  HMAC-SHA256      │                          │  Frontend (React+Vite+TS)    │
│  Token            │                          │       ↓ BFF 代理             │
│                   │                          │  Backend (FastAPI)           │
│                   │                          │    ├─ 本地验签(共享          │
│                   │                          │    │   AUTH_SECRET)          │
│                   │ ← /auth/login 代理 ──────│    ├─ SQLite (上传记录)       │
│                   │                          │    └─ X-API-Key 代理 ───────┐ │
└──────────────────┘                          │                              │ │
                                              │  SQLite (uploads 表)         │ │
                                              └──────────────────────────────┘ │
                                                                               │
                                                                               ▼
                                                                  ┌─────────────────────┐
                                                                  │  WeKnora            │
                                                                  │  REST API           │
                                                                  │                     │
                                                                  │  X-API-Key 鉴权     │
                                                                  │  ingest+retrieve    │
                                                                  └─────────────────────┘
```

### 设计原则

- **BFF 强制代理**:WeKnora API Key 只在 RAGPortal 后端,前端永远不持有
- **零侵入**:WeKnora、AI4MS 主代码均不修改
- **双写兜底**:RAGPortal SQLite 存主记录,同时把 `uploader_id` 塞进 WeKnora `metadata` 字段(冗余,便于反查)
- **懒同步**:不做定时全量同步,解析状态在用户访问页面时按需拉取

## 3. 认证与用户

### Token 格式(复用 AI4MS)

`{base64url(payload)}.{hmac_sha256(payload_b64, AUTH_SECRET)}`

Payload 字段:`sub`(user_id)、`username`、`role`(`admin`/`user`)、`iat`、`exp`

### 双路径登录

**路径 A:门户 SSO 跳转**
1. 用户在 AI4MS 门户点 RAGPortal 卡片
2. 门户 `AppCard` 调 `window.open('https://rag.xxx.com/sso#token=<ai4ms_token>', '_blank')`
3. RAGPortal `/sso` 路由从 `location.hash` 提取 token,存 `sessionStorage`(key: `ai4ms_token`,与 AI4MS 同 key)
4. 清掉 hash,跳转 `/upload`

**路径 B:独立登录页**
1. 用户直接访问 `https://rag.xxx.com`,AuthGuard 检测无 token,跳 `/login`
2. 用户输入用户名/密码,RAGPortal 前端 `POST /api/auth/login` 到本地后端
3. RAGPortal 后端代理调用 AI4MS `POST /auth/login`,拿 token + user 信息
4. 前端存 token,跳 `/upload`

### Token 校验流程(RAGPortal 后端)

完全复用 AI4MS `backend/app/core/auth.py:34-89` 的 `parse_access_token` 逻辑:
1. HMAC-SHA256 验签(用 `AUTH_SECRET` 环境变量)
2. 解码 payload,检查 `exp` 过期
3. 检查 `role ∈ {admin, user}`
4. **不查 AI4MS DB,不查用户当前状态**——信任签名后的 token payload

### 权限模型

| 角色 | 上传 | 看自己历史 | admin 后台 |
|------|------|------------|------------|
| `user` | ✓ | ✓ | ✗ |
| `admin` | ✓ | ✓ | ✓ |

### 已知风险与接受

- AI4MS 禁用某用户后,该用户 token 在过期前仍可操作 RAGPortal(默认几小时窗口)
- 缓解:出现风险用户时,运维直接换 WeKnora API Key 即可瞬间切断所有上传能力

## 4. 上传链路(BFF 代理)

### 完整时序

```
[用户浏览器]
    │  POST /api/uploads   (multipart/form-data: file, kb_id[, custom_filename])
    │  Authorization: Bearer <AI4MS token>
    ↓
[RAGPortal 后端]
    │ ① FastAPI 路由层:验签 token,取出 user_id/username/role/organization
    │ ② 权限校验:role ∈ {admin, user};若 KB 不在该 Key 允许范围 → 403
    │ ③ 文件大小软校验:超过 UPLOAD_MAX_SIZE_MB → 413
    │ ④ 组装 weknora 请求:
    │     POST  {WEKNORA_BASE_URL}/api/v1/knowledge-bases/{kb_id}/knowledge/file
    │     Headers: X-API-Key: <WEKNORA_API_KEY>
    │     Form:    file=<file>
    │              metadata={"uploader_id": user_id, "uploader_name": username, "uploader_org": org}
    │              customFileName=<webkitRelativePath 或原文件名>
    │ ⑤ 调用 weknora(httpx.AsyncClient,30s 超时,失败重试 1 次)
    │ ⑥ 解析响应:
    │     - 200 → 拿 knowledge.id, parse_status="pending"
    │     - 409 (duplicate) → 不落 SQLite,返回特定错误码
    │     - 4xx/5xx → 透传错误信息
    │ ⑦ SQLite 落记录(见 §5)
    │ ⑧ 返回前端:knowledge_id + 初始状态
    ↓
[用户浏览器]   显示"上传成功,处理中"
```

### 关键设计

**KB 列表缓存**
- 后端首次调用 weknora `GET /api/v1/knowledge-bases?allowed_only=true` 拉取该 API Key 能访问的 KB 列表
- 内存缓存(TTL=`KB_LIST_CACHE_TTL`,默认 300 秒),避免每次进页面都请求
- 上传时校验 `kb_id ∈ 缓存集合`,不在缓存则触发一次刷新(避免缓存未预热导致误拒);刷新后仍不在 → 返回 403

**metadata 冗余字段**
- 利用 WeKnora 已有的 `metadata` 入参,塞入 `uploader_id`、`uploader_name`、`uploader_org`
- WeKnora 直接落到 `knowledges.metadata` JSON 列,零改动
- 即便 RAGPortal SQLite 数据丢失,也能从 WeKnora 反查上传者

**文件夹上传**
- 前端用 `<input type="file" webkitdirectory multiple>` 选文件夹;支持拖拽(用 `DataTransferItem.webkitGetAsEntry()` 递归读取)
- 把 `file.webkitRelativePath`(如 `subdir/report.pdf`)作为 `customFileName` 传给 WeKnora,保留目录结构语义
- 过滤隐藏文件:`.DS_Store`、`.git*`、`Thumbs.db`、`__MACOSX/`、`node_modules/` 等

**多文件并发控制**
- 默认 5 并发(`UPLOAD_CONCURRENCY`),用 `p-limit` 或自实现信号量
- 单文件失败不影响其他文件

**文件大小限制**
- 后端做软限制(默认 100MB,`UPLOAD_MAX_SIZE_MB`),超了直接拒绝,不转发到 WeKnora
- WeKnora 自己还有租户存储配额校验,RAGPortal 不重复处理

### 解析状态懒同步

- WeKnora 上传后是异步处理:切块 → 向量化 → 可选摘要/问答生成,`parse_status` 从 `pending` → `processing` → `success`/`failed`
- 用户进 `/my-uploads` 或 admin 进 `/admin/uploads` 时,后端对最近 50 条**非终态**记录(`pending`/`processing`)批量调 WeKnora `GET /api/v1/knowledge/{id}`,更新 SQLite 的 `parse_status` / `parse_error`
- 不做定时全量同步、不做 webhook(WeKnora 也不支持)、不做长连接推送

### 错误处理矩阵

| 场景 | 后端行为 | 前端表现 |
|------|---------|---------|
| Token 无效/过期 | 401 | 顶层拦截器跳 `/login` |
| `role=user` 访问 admin 路由 | 403 | 跳 `/upload` + toast |
| `kb_id` 不在该 Key 允许范围 | 403,提示"无权上传到此知识库" | 上传按钮禁用 + 红色提示 |
| 文件大小超 RAGPortal 软限制 | 413 | 单文件状态显示"超出大小限制" |
| WeKnora API Key 无效 | 启动时探测,失败则禁用整个上传功能 | 顶部红色 banner |
| WeKnora 文件类型不允许 | 透传 4xx 与 WeKnora 的错误 message | 单文件失败,显示原始 message |
| WeKnora 文件 hash 重复 (409) | **不落 SQLite**,返回特定错误码 | 单文件状态显示"文件已存在" |
| WeKnora 配额超限 | 透传 4xx | 顶部 banner 提示配额已满 |
| WeKnora 网络超时/5xx | 重试 1 次后返回失败 | 单文件失败,提示"网络异常,可重试" |

## 5. 数据模型(SQLite)

仅一张表 `uploads`。统计实时算(SQLite 在这个量级足够快),KB 列表走内存缓存,无需额外表。

### 表结构

```sql
CREATE TABLE uploads (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id          TEXT    NOT NULL UNIQUE,
    kb_id                 TEXT    NOT NULL,
    kb_name               TEXT    NOT NULL,
    uploader_user_id      TEXT    NOT NULL,
    uploader_username     TEXT    NOT NULL,
    uploader_organization TEXT    NOT NULL DEFAULT '',
    file_name             TEXT    NOT NULL,
    file_type             TEXT    NOT NULL,
    file_size             INTEGER NOT NULL,
    parse_status          TEXT    NOT NULL DEFAULT 'pending',
    parse_error           TEXT    NOT NULL DEFAULT '',
    weknora_task_id       TEXT    NOT NULL DEFAULT '',
    uploaded_at           TEXT    NOT NULL,
    last_synced_at        TEXT    NOT NULL
);

CREATE INDEX idx_uploads_user_time ON uploads(uploader_user_id, uploaded_at DESC);
CREATE INDEX idx_uploads_kb_time   ON uploads(kb_id, uploaded_at DESC);
CREATE INDEX idx_uploads_status    ON uploads(parse_status);
CREATE INDEX idx_uploads_time      ON uploads(uploaded_at DESC);
```

### 字段语义

| 字段 | 来源 | 说明 |
|------|------|------|
| `knowledge_id` | WeKnora 返回 | 全局唯一,有 UNIQUE 约束防双写 |
| `kb_id` / `kb_name` | 上传时选定 | `kb_name` 冗余快照,KB 改名后旧记录保留原名 |
| `uploader_user_id` | AI4MS token payload | 主标识,用于"看自己历史" |
| `uploader_username` / `uploader_organization` | AI4MS token payload | 冗余快照,用户改名后旧记录保留原值 |
| `file_name` | 前端传入 | 文件夹场景含相对路径(如 `数据/实验结果.xlsx`) |
| `file_type` | RAGPortal 推断(按扩展名) | pdf/docx/xlsx/pptx/md/txt 等 |
| `file_size` | multipart 文件大小 | 字节 |
| `parse_status` | 懒同步更新 | `pending` → `processing` → `success`/`failed` |
| `parse_error` | 懒同步更新 | 失败时存 WeKnora 返回的 error_message |
| `weknora_task_id` | WeKnora 返回(审计日志详情里) | Asynq 任务 ID,运维追溯用 |
| `uploaded_at` | RAGPortal 写入时 | ISO8601 |
| `last_synced_at` | 懒同步更新 | 用于判断是否需要再次同步 |

### 设计决策

- **不存 WeKnora 完整响应**:只存追溯用关键字段(`knowledge_id`、`weknora_task_id`),需要详情时反查 WeKnora
- **不存文件内容/路径**:文件已由 WeKnora 落对象存储,RAGPortal 不存
- **冗余快照字段**:审计语义"当时是谁传的、当时叫什么名",不去 join AI4MS DB
- **`UNIQUE(knowledge_id)`**:兜底防并发或重试导致的双写
- **`parse_status` 不用枚举类型**:SQLite 没有真正的枚举,用 TEXT + 应用层校验

### `parse_status` 状态映射

WeKnora 内部 `parse_status` 有多种细分值,RAGPortal 这边做粗粒度映射,只保留 4 种对外暴露:

| WeKnora 状态 | RAGPortal `parse_status` | UI 徽标 |
|--------------|--------------------------|---------|
| `pending` | `pending` | ⌛ 等待中(灰色) |
| `processing` / `finalizing` / `reprocessing` | `processing` | ⏳ 处理中(蓝色) |
| `success` / `completed` / `enabled` | `success` | ✓ 成功(绿色) |
| `failed` / `error` / 其他 | `failed` | ✗ 失败(红色),`parse_error` 存 WeKnora 原始 message |

懒同步时按上表把 WeKnora 返回值映射到 RAGPortal 状态。终态(`success`/`failed`)不再同步。

## 6. 前端页面结构

### 路由树

```
/login                     → 独立登录页(账号密码)
/sso                       → SSO token 接收(无 UI,自动跳转)
/logout                    → 清 token,回 AI4MS 门户首页

/upload                    → 上传页(所有登录用户)
/my-uploads                → 我的历史(所有登录用户)

/admin                     → 重定向到 /admin/dashboard
/admin/dashboard           → 仪表盘(仅 admin)
/admin/uploads             → 全部上传记录(仅 admin)
```

### 路由守卫

- `AuthGuard`:未登录 → `/login`
- `AdminGuard`:非 admin → 重定向 `/upload`

### 页面职责

**`/login`**
- 表单:用户名 + 密码 + 登录按钮
- 提交后 `POST /api/auth/login`(RAGPortal 后端代理 AI4MS `/auth/login`)
- 底部链接:"前往 AI4MS 注册"(外链到 AI4MS `/register`)

**`/sso`**
- 进页面从 `location.hash` 取 `token`
- 存 `sessionStorage.ai4ms_token`,清 hash,跳 `/upload`
- 无 token → 显示"请从 AI4MS 门户进入"+ 门户跳转链接

**`/upload`(核心)**
- 顶部:KB 选择下拉(数据来自 RAGPortal 后端 `/api/kb/list`)
- 中部:虚线框拖拽区,按钮 `[选择文件]` `[选择文件夹]`
- 底部:本次会话已上传清单,逐文件显示状态徽标(`✓ 成功` / `⏳ 处理中` / `✗ 失败` / `⌛ 等待中`)
- 失败行可展开看错误详情,提供"重新上传"按钮(打开文件选择器)
- 顶部一个总进度条(已完成 / 总数)

**`/my-uploads`**
- 表格:文件名 / KB / 大小 / 状态 / 上传时间
- 进页面时触发后端懒同步最近 50 条非终态记录
- 简单分页(每页 20 条)
- 失败记录可点开看错误详情

**`/admin/dashboard`**
- 4 张 KPI 卡:总上传数 / 本周上传 / 失败数 / 活跃用户(近 7 天)
- 折线图:近 30 天每日上传量
- 柱状图:Top 5 上传者
- 饼图:各 KB 上传分布

**`/admin/uploads`**
- 筛选条:上传者(模糊)/ KB(下拉)/ 状态(下拉)/ 时间范围(date)/ 文件名搜索
- 右上角:`[刷新状态]` 按钮(触发后端懒同步)+ `[导出 CSV]` 按钮(按当前筛选条件导出)
- 表格 6 列:上传者(含组织)/ 文件名 / KB / 大小 / 状态 / 上传时间
- 分页:每页 20 条

### 状态管理(Zustand)

3 个 store:
- `authStore`:`isAuthenticated`、`user`、`login`、`logout`、`initialize`
- `kbStore`:`kbList`、`currentKbId`、`fetchKbList`、`setCurrentKb`
- `uploadStore`:`pendingQueue`、`recentSession`(本次会话)、`enqueueUpload`、`startQueue`

### 顶部导航

```
[◆ RAGPortal]   上传  我的记录  [后台 ▾]              [头像 ▾]
                                                    ├─ 用户名 / 组织
                                                    └─ 退出登录
```

`[后台 ▾]` 下拉仅在 `role=admin` 时显示,展开:`仪表盘` / `上传记录`。

## 7. 视觉风格

采用**简洁专业风**(Notion/Linear 工具型),理由:工具型应用长时间使用不累,后台表格类内容可读性最佳。

### 配色

| 用途 | 值 |
|------|-----|
| 背景 | `#f8fafc` |
| 卡片底 | `#ffffff` |
| 主色 | `#2563eb` |
| 主色悬停 | `#1d4ed8` |
| 文字主 | `#0f172a` |
| 文字次 | `#475569` |
| 文字弱 | `#94a3b8` |
| 边框 | `#e2e8f0` |
| 边框输入 | `#cbd5e1` |

### 状态色

| 状态 | 背景 | 文字 |
|------|------|------|
| 成功 | `#dcfce7` | `#16a34a` |
| 处理中 | `#dbeafe` | `#2563eb` |
| 等待 | `#fef9c3` | `#ca8a04` |
| 失败 | `#fee2e2` | `#dc2626` |

### 布局规范

- 卡片圆角:`8px`
- 按钮:主色填充(白字)、次按钮白底浅边框
- 表格表头:浅灰底 `#f1f5f9`,uppercase + 字间距
- 间距基准:`4px / 8px / 12px / 16px / 20px / 24px`

## 8. 后端 API 设计

### 鉴权相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 代理 AI4MS `/auth/login`,返回 token + user |
| GET | `/api/auth/me` | 验签当前 token,返回 user 信息 |
| POST | `/api/auth/logout` | 无操作(token 自签,后端不存),前端清 sessionStorage 即可 |
| GET | `/api/config` | 返回前端需要的公共配置(`portal_url` 跳转链接、`max_size_mb` 上传上限、`allowed_file_types` 等),不依赖登录 |

### KB 相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kb/list` | 代理 WeKnora `GET /api/v1/knowledge-bases`,返回该 Key 能访问的 KB 列表(带 5 分钟内存缓存) |

### 上传相关

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/uploads` | multipart 单文件上传,后端代理 WeKnora |
| GET | `/api/uploads/mine` | 当前用户上传记录(分页) |
| GET | `/api/uploads/{id}` | 单条记录详情(同时触发该记录的状态懒同步) |

### admin 接口(需 `role=admin`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/uploads` | 全部记录(支持筛选、分页) |
| GET | `/api/admin/uploads/export` | 按当前筛选条件导出 CSV |
| GET | `/api/admin/stats/overview` | 仪表盘 KPI 数据 |
| GET | `/api/admin/stats/daily-trend` | 近 30 天每日上传量(给折线图) |
| GET | `/api/admin/stats/top-uploaders` | Top N 上传者(给柱状图) |
| GET | `/api/admin/stats/kb-distribution` | 各 KB 上传分布(给饼图) |
| POST | `/api/admin/uploads/sync-status` | 触发批量懒同步(对最近 N 条非终态记录) |

## 9. 技术栈

### 前端

| 用途 | 选型 | 版本 |
|------|------|------|
| 框架 | React | 18.x |
| 语言 | TypeScript | 5.x |
| 构建 | Vite | 5.x |
| 样式 | Tailwind CSS | 3.x |
| 路由 | React Router | 7.x |
| 状态 | Zustand | 4.x |
| HTTP | Axios | 1.x |
| 图表 | Recharts | 2.x |
| 文件夹拖拽 | `react-dropzone` + 原生 `webkitdirectory` | — |

### 后端

| 用途 | 选型 | 版本 |
|------|------|------|
| 框架 | FastAPI | 0.110+ |
| 运行 | Uvicorn | — |
| 语言 | Python | 3.11+ |
| DB ORM | SQLAlchemy | 2.x(异步) |
| DB 驱动 | `aiosqlite` | — |
| HTTP 客户端 | `httpx` | — |
| 配置 | Pydantic Settings | v2 |
| 验签 | 标准库 `hmac`/`hashlib`/`base64` | — |
| CORS | FastAPI 自带 `CORSMiddleware` | — |

### 数据库

SQLite + WAL 模式(支持并发读)。文件位于 `backend/data/ragportal.db`。

## 10. 项目结构

```
RAGPortal/
├── README.md
├── .env.example
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── router.tsx
│       ├── api/
│       │   ├── client.ts          # axios 实例 + 拦截器
│       │   ├── auth.ts
│       │   ├── kb.ts
│       │   └── uploads.ts
│       ├── stores/
│       │   ├── authStore.ts
│       │   ├── kbStore.ts
│       │   └── uploadStore.ts
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── NavBar.tsx
│       │   ├── KbSelector.tsx
│       │   ├── UploadDropzone.tsx
│       │   ├── UploadQueueItem.tsx
│       │   ├── StatusBadge.tsx
│       │   └── Pagination.tsx
│       ├── pages/
│       │   ├── LoginPage.tsx
│       │   ├── SsoPage.tsx
│       │   ├── UploadPage.tsx
│       │   ├── MyUploadsPage.tsx
│       │   └── admin/
│       │       ├── DashboardPage.tsx
│       │       └── UploadsAdminPage.tsx
│       └── utils/
│           ├── fileFilter.ts      # 过滤隐藏文件
│           └── format.ts          # 文件大小、时间格式化
└── backend/
    ├── requirements.txt
    ├── pyproject.toml
    ├── data/                       # SQLite 文件(运行时生成,.gitignore)
    └── app/
        ├── main.py                 # FastAPI 入口 + CORS + lifespan
        ├── core/
        │   ├── config.py           # Pydantic Settings
        │   ├── auth.py             # HMAC 验签 + FastAPI 依赖
        │   ├── db.py               # SQLAlchemy session
        │   └── weknora.py          # WeKnora HTTP 客户端
        ├── models/
        │   └── upload.py           # Upload ORM 模型
        ├── api/v1/
        │   ├── auth.py             # /auth/login, /auth/me, /auth/logout
        │   ├── kb.py               # /kb/list
        │   ├── uploads.py          # /uploads, /uploads/mine, /uploads/{id}
        │   └── admin.py            # /admin/uploads, /admin/stats/*
        ├── services/
        │   ├── kb_service.py       # KB 列表缓存
        │   ├── upload_service.py   # 上传 + 双写
        │   └── sync_service.py     # 解析状态懒同步
        └── tests/
            ├── test_auth.py
            ├── test_upload_service.py
            └── test_sync_service.py
```

## 11. 配置项(.env)

```dotenv
# ===== 认证(与 AI4MS 共享)=====
AUTH_SECRET=<与 AI4MS AUTH_SECRET 完全一致>
AUTH_TOKEN_EXPIRE_HOURS=24          # 仅用于本地校验参考,实际以 token 内 exp 为准

# ===== AI4MS 门户对接 =====
AI4MS_BASE_URL=https://ai4ms.xmuzc.com
AI4MS_PORTAL_URL=https://ai4ms.xmuzc.com   # 用于"前往注册"外链

# ===== WeKnora 对接 =====
WEKNORA_BASE_URL=https://weknora.xmuzc.com
WEKNORA_API_KEY=<Scoped API Key with ingest + retrieve>

# ===== 上传限制 =====
UPLOAD_MAX_SIZE_MB=100
UPLOAD_CONCURRENCY=5
ALLOWED_FILE_TYPES=pdf,doc,docx,xls,xlsx,ppt,pptx,md,txt,csv,html

# ===== 缓存 =====
KB_LIST_CACHE_TTL=300

# ===== 数据库 =====
SQLITE_PATH=data/ragportal.db

# ===== CORS(开发期)=====
FRONTEND_ORIGIN=https://rag.xmuzc.com

# ===== 部署 =====
APP_ENV=production                  # production / development
LOG_LEVEL=INFO
```

## 12. AI4MS 门户接入(可选,不强制)

> 用户已明确"不想改动 AI4MS 主代码"。这一节是**可选建议**,是否在 AI4MS 门户首页追加 RAGPortal 入口卡片由用户自行决定。即使不加,用户也可以直接访问 RAGPortal 子域名走独立登录页登录。

若要在 AI4MS 门户暴露入口,只需在 AI4MS `frontend/src/pages/HomePage.tsx` 的 `APPS` 数组追加一项(纯配置追加,不涉及逻辑改动):

```ts
{
  name: 'RAG 知识库',
  description: ['文档上传', '知识库管理'],
  icon: '📚',
  accentColor: '#2563eb',
  accentTextClass: 'var(--accent-blue-text)',
  url: 'https://rag.xmuzc.com',
}
```

AppCard 已实现的 `window.open(${url}#token=${token})` 机制会自动把 AI4MS token 通过 hash 传给 RAGPortal,无需额外改动。

## 13. 测试策略

按用户偏好,仅对核心业务逻辑写必要测试,不写覆盖率的"全能测试"。

**必写测试**:
- `test_auth.py`:HMAC 验签正确性、过期拒绝、伪造拒绝
- `test_upload_service.py`:上传成功路径、WeKnora 错误透传、metadata 注入、SQLite 双写
- `test_sync_service.py`:懒同步状态更新逻辑

**不写测试**:
- API 路由层(业务逻辑在 service,薄薄一层路由不必测)
- 前端组件(简单 UI,手动测试覆盖)
- 配置加载、日志

## 14. 部署

参考 AI4MS 现有方式(`ecosystem.config.js` + pm2):

```js
// ecosystem.config.js
module.exports = {
  apps: [
    {
      name: 'ragportal-backend',
      script: 'backend/venv/bin/uvicorn',
      args: 'app.main:app --host 127.0.0.1 --port 8002',
      cwd: './',
      env: { APP_ENV: 'production' },
    },
    {
      name: 'ragportal-frontend',
      script: 'frontend/node_modules/vite/bin/vite.js',
      args: 'preview --port 3002 --host',
      cwd: './',
    },
  ],
}
```

反代(Nginx)将 `rag.xmuzc.com` → 前端静态文件 + `/api/*` → 后端 8002。

## 15. 不在范围内(YAGNI)

明确不做的事:

- ❌ 文档删除接口(admin 也不删,需要时去 WeKnora 主后台删)
- ❌ 知识库管理(创建/修改 KB)
- ❌ 向量化参数、切块策略等高级配置(走 WeKnora 默认)
- ❌ 用户管理(RAGPortal 不维护用户表)
- ❌ 操作审计日志(RAGPortal 自身不审计,依赖 WeKnora `audit_logs`)
- ❌ WebSocket / SSE 实时推送
- ❌ 全文搜索(只支持文件名模糊匹配)
- ❌ 国际化(只支持中文)
- ❌ 暗色模式

## 16. 后续可扩展点(本期不做)

留口子,但不在当前需求里:

- **重传历史文件**:基于 `parse_error` 字段筛选失败记录,提供批量重传按钮
- **admin 强制下线**:对在线 token 加缓存黑名单(短期 Redis)
- **批量导出**支持 Excel 格式
- **API Key 多 Key 管理**(若未来一个 RAGPortal 服务多个租户)
