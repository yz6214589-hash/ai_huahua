# 交易官 Ethan（本地启动与联调）

## 端口约定（默认）

- 后端 FastAPI：`http://127.0.0.1:8001`
- 前端 Vite：`http://127.0.0.1:5178`（端口可变）

## 启动后端

在 `ethan/backend` 目录：

```bash
python3 -m uvicorn ethan_api.app:app --host 127.0.0.1 --port 8001
```

健康检查：

```bash
curl http://127.0.0.1:8001/api/health
```

## 启动前端

在 `ethan/frontend` 目录：

```bash
npm run dev -- --host 127.0.0.1 --port 5178
```

打开：

```text
http://127.0.0.1:5178/
```

## API 地址与 CORS

- 前端默认请求地址：`{当前页面协议}://{当前页面hostname}:8001`
- 如需覆盖后端地址：
  - 设置环境变量 `VITE_ETHAN_API_BASE`（例如 `http://127.0.0.1:8001` / `http://localhost:8001`）

- 后端 CORS：
  - 默认允许本地开发常见 Origin（`localhost/127.0.0.1` 的任意端口）
  - 如需收敛放行范围，可设置 `ETHAN_CORS_ORIGINS`（逗号分隔）

## 外部依赖与环境变量

### MiniQMT（实盘）

需要环境变量：

- `QMT_PATH`
- `ACCOUNT_ID`

并确保 MiniQMT 客户端已启动且已登录（依赖 `xtquant` 环境）。

### MySQL（训练/回测/仿真数据源）

需要环境变量：

- `WUCAI_SQL_HOST`
- `WUCAI_SQL_PORT`
- `WUCAI_SQL_USERNAME`
- `WUCAI_SQL_PASSWORD`
- `WUCAI_SQL_DB`

