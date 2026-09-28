# RAGPortal

AI⁴MS 子应用 — 独立的知识库文档上传门户。

- **前端**:React + Vite + TypeScript(`frontend/`)
- **后端**:Python + FastAPI(`backend/`)
- **认证**:复用 AI4MS HMAC Token(共享 `AUTH_SECRET`)
- **文档存储**:WeKnora(通过 `X-API-Key` 调用,不修改 WeKnora 主代码)
- **MCP 网关**:RAGPortal `/api/mcp`(账户级 API Token 鉴权,代理 WeKnora)

## WorkBuddy MCP 接入

登录 RAGPortal 后打开“API Token”，创建 Token 并勾选需要的权限。明文只显示一次。

```json
{
  "mcpServers": {
    "ragportal": {
      "type": "streamable-http",
      "url": "https://你的域名/api/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_TOKEN"
      }
    }
  }
}
```

外部 MCP 客户端只访问 RAGPortal，不能直接访问 WeKnora、数据库或 AI4MS 密码。创建 Token 时必须绑定知识库，并勾选文档列表、检索、读取、下载和写入等权限。

`rag_search` 不传 `kb_id` 或 `kb_ids` 时检索 Token 绑定的全部知识库。需要限定范围时，可以先调用 `rag_list_knowledge_bases` 获取 ID，再传 `kb_id`（单库）或 `kb_ids`（多库）；两种范围参数不能同时提供。未绑定的库不能被检索。

```json
{"query": "实验条件", "top_k": 10}
```

```json
{"query": "实验条件", "kb_ids": ["kb-a", "kb-b"], "top_k": 10}
```

`top_k` 是最终结果总数（1 到 20，默认 5）。跨库按各库内部排名交错合并，不直接比较不同库的分数；每条命中带 `kb_id`、`kb_name` 和原始文档来源字段。部分库失败时返回 `partial: true` 和 `errors`，全部失败则返回错误。

`rag_list_knowledge_bases` 从 WeKnora 读取知识库列表并按 Token 绑定范围过滤；`rag_list_documents` 直接从 WeKnora 分页列出指定知识库的全部文档（`kb_id` 必填，`page`、`page_size` 可选）。列表中的 `document_id` 是 WeKnora 文档 ID，可继续传给 `rag_get_document` 和 `rag_download_file`。RAGPortal 本地 `uploads` 表仅用于门户上传日志，不作为 MCP 文档清单的数据源。

所有 MCP 文档工具统一使用 WeKnora 文档 ID（字符串）作为 `document_id`。`rag_search` 的每条命中和 `rag_upload_document` 的返回值都提供该字段；上传结果另用 `upload_id` 表示 RAGPortal 本地记录 ID，并保留 `knowledge_id` 兼容原有调用。

上传后可用 `rag_get_upload_status` 和返回的 `document_id` 查询 WeKnora 的实时处理状态。此工具需要 `documents:write` 权限，只能查询 Token 所属用户上传、且仍在 Token 绑定知识库中的文档；返回 `parse_status`、`enable_status`、`error_message` 和 `checked_at`。`parse_status` 保留 WeKnora 的 `pending`、`processing`、`finalizing`、`completed`、`failed`、`cancelled` 原值；上游文档已不存在时返回 `deleted`。只有 `completed` 表示解析与后续处理结束，上传接口返回成功并不代表处理完成。

检索命中包含 WeKnora `image_info` 时，RAGPortal 会将图片说明和短期链接写入该字段的 `caption` 和 `markdown_url`。链接由后端在已授权知识库内代理读取，默认有效 30 天，最多返回 3 张，只接受 JPEG、PNG、WebP 和 GIF。`resource://` 引用不会暴露给外部客户端，非多模态模型也可以根据这些字段生成带图片的 Markdown 回复。

部署到外部 Agent 使用时必须设置 `MCP_PUBLIC_BASE_URL=https://你的 RAGPortal 公网域名`；本地开发才允许回退到 `FRONTEND_ORIGIN`。不能把 `localhost` 或 `127.0.0.1` 作为外部客户端图片地址。

`rag_search` 的 `content` 仅包含一个文本结果块，返回清理后的结构化 JSON，兼容只读取 MCP `content` 的外部 Agent；同时保留 `structuredContent` 供支持结构化输出的客户端解析。结果不包含 WeKnora 内部 `metadata`、重复的 `matched_content` 或冗长图片 OCR。图片说明和链接保留在 JSON 的 `image_info` 中，不再额外追加图片 Markdown 文本块。

### 短期文件下载

`rag_download_file` 使用当前 API Token 签发仅针对指定文档的下载链接，返回 `download_url`、`expires_at` 和文件名。链接有效期为 10 分钟，期间可重复访问；打开链接无需再提供 API Token。服务端每次访问都会重新检查原 Token 是否有效、是否仍有下载权限、知识库绑定是否保留，以及 WeKnora 文档是否仍属于该知识库。过期后重新调用工具即可获取新链接。原 `/api/mcp/files/{document_id}` Bearer 下载入口仍可用。

在生产环境配置 `MCP_PUBLIC_BASE_URL=https://你的 RAGPortal 域名`，不配置时回退到 `FRONTEND_ORIGIN`。外网下载链接必须使用 HTTPS。下载凭证明文只出现在短期链接中，数据库仅保存摘要；不要将完整下载 URL 写入日志或长期保存。

## 设计文档

- [设计 spec](docs/specs/2026-07-31-ragportal-design.md)
- [实施计划](docs/plans/2026-07-31-ragportal.md)

## 本地开发

```bash
# 后端
cd backend
conda activate ragportal
pip install -r requirements.txt
cp ../.env.example ../.env      # 修改其中的密钥与域名
uvicorn app.main:app --reload --port 8004

# 前端(另开终端)
cd frontend
npm install
npm run dev                     # 默认 3002 端口,自动代理 /api → 后端
```

## 部署

```bash
# 1. 安装依赖
cd backend && conda activate ragportal && pip install -r requirements.txt && cd ..
cd frontend && npm install && npm run build && cd ..

# 2. 配置 .env(含 AUTH_SECRET / WEKNORA_API_KEY / 域名)
cp .env.example .env && vim .env

# 3. 启动(pm2)
pm2 start ecosystem.config.cjs
pm2 save
```

## Nginx 反向代理(示例)

生产环境须在 Nginx 或上层代理启用 HTTPS；下例只展示反向代理路径，不能单独作为短期下载链接的 TLS 配置。

```nginx
server {
    listen 80;
    server_name rag.xmuzc.com;

    location /api/mcp/downloads/ {
        access_log off;
        proxy_pass http://127.0.0.1:8004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://127.0.0.1:8004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 100M;
    }
}
```

## AI4MS 门户接入(可选)

在 AI4MS `frontend/src/pages/HomePage.tsx` 的 `APPS` 数组追加:

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

AppCard 会自动通过 `window.open(url#token=xxx)` 把 AI4MS token 通过 hash 传给 RAGPortal,实现 SSO。
