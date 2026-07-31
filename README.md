# RAGPortal

AI⁴MS 子应用 — 独立的知识库文档上传门户。

- **前端**:React + Vite + TypeScript(`frontend/`)
- **后端**:Python + FastAPI(`backend/`)
- **认证**:复用 AI4MS HMAC Token(共享 `AUTH_SECRET`)
- **文档存储**:WeKnora(通过 `X-API-Key` 调用,不修改 WeKnora 主代码)

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
