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
python -m venv venv
source venv/Scripts/activate    # Windows Git Bash; PowerShell 用 venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env      # 修改其中的密钥与域名
uvicorn app.main:app --reload --port 8002

# 前端
cd frontend
npm install
npm run dev                     # 默认 3002 端口,自动代理 /api 到后端
```

## 部署

详见 [README 部署章节](README.md#部署) (Task 18 完成后补充)。
