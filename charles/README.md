# 数字员工情报官 Charles（数据采集 / 清洗 / 交付）

Charles 是 AI 量化交易系统的输入端（Input）：负责对接 QMT / AkShare / Tushare 等数据源，进行数据清洗与标准化落库（MySQL），并通过 Web 控制台提供任务运行、数据浏览与导出交付。

本仓库中 `../week1/`、`../week2/` 为课程示例代码；本项目落地代码位于本目录下：
- 后端（FastAPI）：`api/`
- 前端（React Web 控制台）：`web/`
- MySQL 建库与表结构：`../wucai_trade_schema_show_create.sql`
- Charles 扩展表（股票代码-企业名称映射）：`sql/wucai_trade_charles_extra.sql`

## 数据源优先级规则（强制）

- 日线：QMT → Tushare → AkShare
- 财务：QMT → Tushare → AkShare
- 换手率：仅按 QMT 口径计算（非 QMT 来源时写 `NULL`）
- 宏观经济指标：AkShare
- 财经日历：AkShare
- 新闻事件：AkShare + LLM（可选，需配置 Key 才会生成 summary/更精细情绪）
- 机构研报：AkShare
- 催化剂事件：Qwen Max 联网搜索（DashScope 兼容 OpenAI 接口）

## 1) MySQL 初始化

1. 创建数据库并建表（MySQL 8.0）：执行 `../wucai_trade_schema_show_create.sql`
2. 初始化 Charles 扩展表：执行 `sql/wucai_trade_charles_extra.sql`
2. 确保你的 MySQL 账号具备建库/建表权限，或先让 DBA 代执行

## 2) 后端启动（FastAPI）

### 2.1 Python 环境

建议使用虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```bash
pip install -r api/requirements.txt
```

### 2.2 环境变量

复制 `.env.example` 为 `.env`，按需填写：

```bash
copy .env.example .env
```

主要变量：
- `WUCAI_SQL_HOST` / `WUCAI_SQL_PORT` / `WUCAI_SQL_USERNAME` / `WUCAI_SQL_PASSWORD` / `WUCAI_SQL_DB`
- `TUSHARE_TOKEN`（可选，日线/财务的降级链需要）
- `DASHSCOPE_API_KEY`（可选，关键催化剂需要；新闻 LLM 也可用）
- `KIMI_API_KEY`（可选，新闻 LLM 摘要可用）

### 2.3 运行

```bash
python api/run_server.py
```

默认监听：`http://localhost:8000`

接口：
- `GET /api/health`
- `GET /api/summary`
- `GET /api/stocks`
- `POST /api/stocks/sync`（scope=daily|all）
- `GET /api/stocks/sync/status`
- `POST /api/jobs/run`
- `GET /api/jobs/runs`
- `GET /api/jobs/schedules`
- `PUT /api/jobs/schedules/{domain}`
- `GET /api/data/{dataset}`
- `POST /api/export`
- `GET /api/watchlist`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{stock_code}`
- `PUT /api/watchlist/{stock_code}/pin`
- `PUT /api/watchlist/reorder`
- `GET /api/stock/{stock_code}/snapshot`
- `GET /api/stock/{stock_code}/fundamentals`
- `GET /api/stock/{stock_code}/technical/latest`
- `GET /api/stock/{stock_code}/technical/series`
- `GET /api/stock/{stock_code}/feed`

任务运行记录会写到：`.charles/job_runs/`（JSON 文件），用于 Web 展示。

## 3) 前端启动（Web 控制台）

```bash
cd web
npm install
npm run dev
```

默认地址：`http://localhost:5173`

前端通过 Vite 代理访问后端：`/api -> http://localhost:8000/api`

## 6) 一键启动（开发）

方式一：双击运行：

- `scripts/start_all.cmd`

方式二：PowerShell 执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_all.ps1
```

该脚本会启动两个独立窗口：

- 后端（FastAPI）：`http://localhost:8000`
- 前端（Vite Dev）：`http://localhost:5173`

## 4) 使用方式

1. 打开 Web 控制台：总览（Dashboard）查看数据表最新日期与最近任务运行
2. 进入“采集任务（Jobs）”点击运行
   - 初次建议用 `test` 模式（默认以 `600519.SH` 验证链路）
3. 进入“数据与交付（Data）”浏览表数据，按条件筛选并导出 CSV/JSON
4. 进入“自选股（Watchlist）”搜索并添加股票；支持拖拽排序、删除、置顶；点击进入个股详情（基本面/技术面/新闻研报）

## 6) 采集任务定时调度

后端启动后会读取并初始化 `trade_job_schedule`，并在进程内创建定时任务（默认未开启热重载）。

- 查看各任务的周期/下次执行时间：`GET /api/jobs/schedules`
- 修改任务周期（cron）：`PUT /api/jobs/schedules/{domain}`

## 7) 生产构建 / 部署说明

### 7.1 前端（Web 控制台）

构建：

```bash
cd web
npm install
npm run build
```

构建产物位于：`web/dist/`，将其作为静态站点目录部署即可。

Nginx 示例（静态资源 + /api 反向代理）：

```nginx
server {
  listen 80;
  server_name your.domain.com;

  root /var/www/charles/web/dist;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }

  location /api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

### 7.2 后端（FastAPI）

生产启动（示例）：

```bash
cd api
python -m uvicorn charles_api.app:app --host 0.0.0.0 --port 8000
```

生产环境变量：

- 将 `.env.example` 复制为 `.env`，并在生产机器上填写 MySQL 连接信息
- 如需催化剂/新闻 LLM，配置 `DASHSCOPE_API_KEY` 或 `KIMI_API_KEY`
- 如需日线/财务数据源降级链，配置 `TUSHARE_TOKEN`

跨域（CORS）：

- 开发环境默认允许 `http://localhost:5173`
- 生产环境将 `CHARLES_CORS_ORIGINS` 配置为你的站点域名（例如 `https://your.domain.com`）

## 5) 常见问题

### 5.1 QMT 不可用

日线/财务任务会按规则自动降级到 Tushare / AkShare。若你希望使用 QMT 主数据源：
- 本机安装并启动 miniQMT
- Python 环境可 import `xtquant`

### 5.2 关键催化剂联网搜索无法运行

需要配置 `DASHSCOPE_API_KEY`（阿里云 DashScope），并确保网络可访问。

### 5.3 新闻摘要（LLM）不生成

新闻任务默认会尝试调用 LLM 生成 `summary` 与 `sentiment`（失败则回退到规则词典情绪）。你需要至少配置一个 Key：
- `KIMI_API_KEY` 或 `DASHSCOPE_API_KEY`

## 8) 测试

后端（pytest）：

```bash
cd api
pip install -r requirements-dev.txt
python -m pytest -q --cov=charles_api --cov-fail-under=80
```

前端（vitest）：

```bash
cd web
npm install
npm run test:run
```

端到端（Playwright）：

```bash
cd web
npm run e2e
```
