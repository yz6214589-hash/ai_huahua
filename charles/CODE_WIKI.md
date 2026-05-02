# Code Wiki：Charles（数字员工情报官）

Charles 是一个全栈数据采集与交付系统：后端用 FastAPI 负责“多数据源采集 → 清洗/标准化 → MySQL 落库 → 任务调度与运行记录 → 数据浏览与导出 API”，前端用 React + Vite 提供可视化控制台（任务运行、数据浏览导出、自选股、个股详情）。

项目根目录：[`/Users/apple/Desktop/ai_huahua/charles`](file:///Users/apple/Desktop/ai_huahua/charles)

---

## 1. 目录结构

```
charles/
  api/                           # 后端（FastAPI）
    charles_api/
      app.py                     # FastAPI 应用工厂 + 路由聚合 + 调度器
      config.py                  # Settings + .env 环境变量加载
      db.py                      # MySQL 访问封装
      models.py                  # Pydantic 模型与枚举
      job_store.py               # 任务运行记录（JSON）读写
      cleaning/
        ohlcv.py                 # OHLCV 清洗
      jobs/                      # 各采集任务实现（按 domain 拆分）
        stock_daily.py
        stock_financial.py
        stock_news.py
        macro_indicator.py
        rate_daily.py
        calendar.py
        report_consensus.py
        catalyst.py
        common.py                # JobStats 等公共结构
    run_server.py                # 开发启动入口（uvicorn）
    tests/                       # 后端 pytest 用例（API/清洗/自选股等）
  web/                           # 前端（React + TS + Vite）
    src/
      main.tsx                   # React 入口
      App.tsx                    # 路由表
      api/                       # 前端 API client 与类型
      components/                # 通用组件（AppShell、Card、Tabs 等）
      pages/                     # 页面（Dashboard/Jobs/Data/Watchlist/StockDetail）
      lib/                       # 工具函数
      hooks/                     # hooks
    vite.config.ts               # dev server 代理 /api -> 后端
    package.json                 # 前端依赖与脚本
  scripts/                       # Windows 一键启动脚本
  sql/                           # Charles 扩展 SQL（股票代码-名称映射等）
  .charles/job_runs/             # 任务运行记录（JSON，可配置路径）
  README.md                      # 项目说明与启动方式
```

---

## 2. 整体架构

### 2.1 数据流（从采集到交付）

1. **任务触发**：Web 控制台手动触发或后端定时调度（cron）
2. **数据采集**：按任务域（JobDomain）从 QMT / Tushare / AkShare / 联网搜索等取数
3. **数据清洗与标准化**：对齐字段、去重、数值化、合法性校验
4. **落库（MySQL）**：写入 `huahua_trade` 库的各业务表（OHLCV/财务/新闻/宏观/日历等）
5. **运行记录**：任务执行过程以 JSON 形式写入 `.charles/job_runs/`（供 Web 展示）
6. **交付与查询**：前端通过 `/api/data/{dataset}` 浏览数据，通过 `/api/export` 导出 CSV/JSON

### 2.2 服务分层（后端内部）

- **配置层**：读取 `.env`，拼装 Settings（MySQL、CORS、LLM Key、job store 路径）
- **存储层**：MySQL 访问封装 + 运行记录本地 JSON 文件存储
- **任务层**：按 domain 拆分的采集任务（jobs/*）
- **API 层**：路由聚合、调度器管理、数据查询与导出、个股详情、自选股等

---

## 3. 后端（FastAPI）

### 3.1 入口与启动方式

- 开发启动入口（uvicorn）：[api/run_server.py](file:///Users/apple/Desktop/ai_huahua/charles/api/run_server.py)
  - `CHARLES_RELOAD=1` 可开启热重载
- FastAPI 应用与路由聚合：`create_app()` 位于 [charles_api/app.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/app.py#L34)
  - 模块末尾创建 `app = create_app()`（供 `uvicorn charles_api.app:app` 使用）

### 3.2 配置与环境变量（config.py）

[charles_api/config.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/config.py)

- `Settings` 字段：
  - MySQL：`WUCAI_SQL_HOST/PORT/USERNAME/PASSWORD/DB`
  - CORS：`CHARLES_CORS_ORIGINS`（默认 `http://localhost:5173`）
  - 运行记录目录：`CHARLES_JOB_STORE_DIR`（默认 `{cwd}/.charles/job_runs`）
  - LLM/联网搜索：
    - `DASHSCOPE_API_KEY`（催化剂、也可做新闻 LLM）
    - `QWEN_MODEL`（默认 `qwen-max`）
    - `KIMI_API_KEY`、`KIMI_BASE_URL`、`KIMI_MODEL`
- `load_settings()` 会调用 `load_dotenv()`，自动读取 `.env`

### 3.3 MySQL 访问封装（db.py）

[charles_api/db.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/db.py)

- `MySQLConfig`：MySQL 连接参数
- `connect(cfg)`：建立连接（`autocommit=False`，由上层显式 `commit()`）
- `query_dict(conn, sql, params)`：以 DictCursor 返回列表
- `execute(conn, sql, params)` / `executemany(conn, sql, rows)`：写入类操作

### 3.4 核心模型（models.py）

[charles_api/models.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/models.py)

- `JobDomain`：任务域枚举
  - `stock_daily/stock_financial/stock_news/macro_indicator/rate_daily/report_consensus/calendar/catalyst`
- `DataSource`：数据源枚举
  - `qmt/tushare/akshare/qwen_search/file/unknown`
- `JobRunRequest`：触发任务请求体（domain/mode/params）
- `JobRunResult`：任务运行结果（runId、status、最终数据源、fallback 链、写入行数、失败项等）
- `ExportRequest`：导出请求体（dataset/format/filters/limit）

### 3.5 运行记录存储（job_store.py）

[charles_api/job_store.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/job_store.py)

- `write_run(store_dir, run)`：将 `JobRunResult` 写为 JSON（UTF-8，`ensure_ascii=False`）
- `list_runs(store_dir, domain, limit)`：读取并按 startedAt 倒序返回
- `read_run(store_dir, run_id)`：读取单次运行 JSON
- `init_running(domain)`：创建 status=running 的初始运行对象

### 3.6 调度器与表初始化（app.py）

`create_app()` 在启动阶段会做三件非常关键的事情（都在 [app.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/app.py#L34-L220)）：

1. **确保业务表存在（自动建表）**
   - `trade_stock_master`：股票代码-名称映射（用于搜索与补齐）
   - `trade_watchlist`：自选股（置顶/排序）
   - `trade_job_schedule`：任务调度表（cron/启停/参数）
2. **初始化默认 cron**
   - `_ensure_default_schedules()` 会在 `trade_job_schedule` 为空时写入默认调度配置（如 stock_news 每 10 分钟等）
3. **APScheduler 调度**
   - 可用时创建 `BackgroundScheduler`
   - `_reschedule_all()` 从 DB 读取 `trade_job_schedule` 并注册 CronTrigger
   - 每个 domain 使用一个 `threading.Lock` 防止并发重入（同域同时触发时直接跳过）

### 3.7 任务体系（jobs/*）

任务实现位于：[charles_api/jobs/](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs)

公共统计结构：[common.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs/common.py)

- `JobStats(items_processed, rows_written, failed_items, data_source_final, fallback_chain, message)`

任务列表（与 `JobDomain` 一一对应）：

- `stock_daily`：[stock_daily.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs/stock_daily.py)
  - 特点：优先 QMT（xtquant）；失败则按 tushare/akshare 降级
  - 换手率：仅 QMT 口径计算（非 QMT 时写 `None`）
  - 清洗：对 OHLCV DataFrame 走 `clean_ohlcv_frame()`（见 3.8）
- `stock_financial`：[stock_financial.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs/stock_financial.py)
  - 特点：财务同样按 QMT → Tushare → AkShare 降级
  - 统一字段并 upsert 到 `trade_stock_financial`
- `stock_news`：[stock_news.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs/stock_news.py)
  - 特点：AkShare 拉取新闻；可选调用 LLM 生成摘要与情绪
- `macro_indicator`：[macro_indicator.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs/macro_indicator.py)
- `rate_daily`：[rate_daily.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs/rate_daily.py)
- `calendar`：[calendar.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs/calendar.py)
- `report_consensus`：[report_consensus.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs/report_consensus.py)
- `catalyst`：[catalyst.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/jobs/catalyst.py)
  - 特点：Qwen 联网搜索（DashScope OpenAI 兼容接口），写入日历表并标记 source

### 3.8 清洗逻辑（cleaning/ohlcv.py）

[cleaning/ohlcv.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/cleaning/ohlcv.py)

- `clean_ohlcv_frame(df)`：
  - 数值化：open/high/low/close/amount/volume
  - 丢弃关键列缺失
  - OHLC 合法性校验（low<=high、open/close 在区间内等）
  - 去重与按 index 排序

---

## 4. 后端 API（路由分组）

路由集中在 [charles_api/app.py](file:///Users/apple/Desktop/ai_huahua/charles/api/charles_api/app.py)。按用途可分为：

- **基础**
  - `GET /api/health`
  - `GET /api/summary`
- **任务运行与记录**
  - `POST /api/jobs/run`
  - `GET /api/jobs/runs`
  - `GET /api/jobs/runs/{run_id}`
- **任务调度**
  - `GET /api/jobs/schedules`
  - `PUT /api/jobs/schedules/{domain}`
- **股票主数据**
  - `GET /api/stocks`
  - `POST /api/stocks/sync`
  - `GET /api/stocks/sync/status`
- **个股详情**
  - `GET /api/stock/{stock_code}/snapshot`
  - `GET /api/stock/{stock_code}/fundamentals`
  - `GET /api/stock/{stock_code}/technical/latest`
  - `GET /api/stock/{stock_code}/technical/series`
  - `GET /api/stock/{stock_code}/feed`
- **自选股**
  - `GET /api/watchlist`
  - `POST /api/watchlist`
  - `DELETE /api/watchlist/{stock_code}`
  - `PUT /api/watchlist/{stock_code}/pin`
  - `PUT /api/watchlist/reorder`
- **数据浏览与导出**
  - `GET /api/data/{dataset}`
  - `POST /api/export`

---

## 5. 前端（React Web 控制台）

### 5.1 入口与路由

- React 入口：[web/src/main.tsx](file:///Users/apple/Desktop/ai_huahua/charles/web/src/main.tsx)
- 路由表：[web/src/App.tsx](file:///Users/apple/Desktop/ai_huahua/charles/web/src/App.tsx)
  - `/`（Home/Dashboard）
  - `/jobs`（任务）
  - `/data`（数据与导出）
  - `/watchlist`（自选股）
  - `/stock/:code`（个股详情）

### 5.2 API 访问约定

- `fetchJson` / `postJson`：[web/src/api/client.ts](file:///Users/apple/Desktop/ai_huahua/charles/web/src/api/client.ts)
- Dev 代理：`/api -> http://localhost:8000`：[web/vite.config.ts](file:///Users/apple/Desktop/ai_huahua/charles/web/vite.config.ts#L7-L15)

### 5.3 页面职责（建议阅读入口）

- 任务页：[pages/Jobs.tsx](file:///Users/apple/Desktop/ai_huahua/charles/web/src/pages/Jobs.tsx)
  - 展示 runs 与 schedules
  - 支持把“间隔/单位/开始时间”转换为 cron 并调用 `PUT /api/jobs/schedules/{domain}`
  - 支持运行任务 `POST /api/jobs/run`（默认 test_stock=600519.SH）
- 数据页：`pages/Data.tsx`（数据浏览与导出）
- 自选股：`pages/Watchlist.tsx`（拖拽排序、置顶等）
- 个股详情：`pages/StockDetail.tsx`（快照/基本面/技术面/新闻研报）

---

## 6. 依赖关系

### 6.1 后端依赖

- Python 依赖文件：[api/requirements.txt](file:///Users/apple/Desktop/ai_huahua/charles/api/requirements.txt)
  - `fastapi` / `uvicorn` / `pymysql` / `python-dotenv` / `pandas`
  - 数据源：`akshare` / `tushare`
  - LLM：`openai`（用于 OpenAI 兼容接口调用 DashScope/Kimi）
  - 重试与调度：`tenacity` / `APScheduler`

### 6.2 前端依赖

- Node 依赖文件：[web/package.json](file:///Users/apple/Desktop/ai_huahua/charles/web/package.json)
  - React / Router / ECharts / Tailwind
  - DnD（自选股拖拽）：`@dnd-kit/*`
  - 测试：Vitest / Playwright

### 6.3 外部依赖

- MySQL（`huahua_trade`）：用于存储采集结果、调度配置、自选股等
- 可选：QMT（xtquant）：用于日线与财务的主数据源
- 可选：Tushare Token：用于降级链
- 可选：DashScope/Kimi Key：用于催化剂联网搜索与新闻摘要

---

## 7. 运行方式（开发/部署）

完整步骤见 [README.md](file:///Users/apple/Desktop/ai_huahua/charles/README.md)。

### 7.1 MySQL 初始化

- 执行仓库根目录建表脚本：`../huahua_trade_schema_show_create.sql`
- 执行 Charles 扩展 SQL：`sql/huahua_trade_charles_extra.sql`

### 7.2 后端启动（FastAPI）

```bash
pip install -r api/requirements.txt
python api/run_server.py
```

默认：`http://localhost:8000`

### 7.3 前端启动（Web 控制台）

```bash
cd web
npm install
npm run dev
```

默认：`http://localhost:5173`，通过 Vite proxy 转发 `/api` 到后端。

### 7.4 一键启动（Windows）

- `scripts/start_all.cmd`
- `scripts/start_all.ps1`

