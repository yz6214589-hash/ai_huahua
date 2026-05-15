# AI Quant Unified System

统一 AI 量化系统入口：
- 后端：FastAPI（`backend/`）
- 主前端：React（`web/`，样式基于 Charles）
- AI 对话机器人：Streamlit（`streamlit_chat/`）

## 默认入口（迁移后）

- 默认开发与联调入口：`ai_quant/`
- 一键启动（Windows）：
  - PowerShell：`./scripts/start_all.ps1`
  - CMD：`./scripts/start_all.cmd`
- 统一访问地址：
  - React：`http://localhost:5173`
  - FastAPI：`http://localhost:8000`
  - Streamlit Chat：`http://localhost:8501`

## 迁移期保留策略

- `charles/`、`zoe/`、`ethan/`、`kris/`、`ceo/` 工程继续保留。
- 这些原工程仅用于能力对照、问题回归、历史兼容验证，不再作为默认入口。
- 新增需求、联调与演示默认在 `ai_quant/` 完成，避免多入口并行导致口径不一致。

## 启动

1. 后端

```bash
cd backend
pip install -r requirements.txt
python3 run_server.py
```

2. React

```bash
cd web
npm install
npm run dev
```

3. Streamlit Chat

```bash
cd streamlit_chat
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```
