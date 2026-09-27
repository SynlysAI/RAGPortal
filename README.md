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

客户端调用顺序建议为：先调用 `rag_list_knowledge_bases` 获取该 Token 可访问的知识库，再把返回的 `kb_id` 传给 `rag_search`。`rag_list_documents` 可列出当前账户在该知识库的上传记录。未绑定的知识库不会出现在列表中，也不能被检索、读取、下载或写入。

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

```nginx
server {
    listen 80;
    server_name rag.xmuzc.com;

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
