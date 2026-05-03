# Code Wiki：ai_huahua

本仓库包含“落地系统 + 课程代码（统一放在 `lesson/`）”。落地系统以“数据采集 → 分析决策 → 交易执行 → 风控审计 → CEO 控制台整合”为主线，核心模块包括：

- **Charles（数字员工情报官）**：数据采集/清洗/落库（MySQL）+ 数据交付（API/Web）+ 舆情监控 + 研报生成 + 助手能力（API/Web）
- **Zoe（数字员工分析师）**：指标/信号/选股/回测 + 主力识别 + 绩效分析（API/Web）
- **Ethan（交易官）**：交易执行与任务编排（含 QMT 连接、执行任务、RL 训练/回测、WebSocket 事件）
- **Kris（风控官）**：风控决策引擎（审批、ATR 止损、宏观门控、审计日志、风控状态）
- **CEO 控制台（ceo/）**：整合型 Web 工作台（实盘/模拟盘监控、回测、晨会、投研对话、调度）
- **lesson/**：课程周代码（`lesson/week1` ~ `lesson/week11`）

---

## 1. 仓库目录结构（Top-Level）

> 以“可落地工程”为主线；课程代码已迁移至 `lesson/`。

```
ai_huahua/
  charles/                       # 情报官：采集/清洗/落库/交付 + 舆情/研报/助手
  zoe/                           # 分析师：指标/信号/选股/回测 + 主力识别 + 绩效分析
  ethan/                         # 交易官：执行引擎 + QMT + RL + Web 控制台
  kris/                          # 风控官：风控引擎 + 审批/审计 Web 控制台
  ceo/                           # CEO 控制台：整合型 Web 工作台（晨会/投研/实盘/回测/调度）
  lesson/                        # 课程周代码：lesson/week1 ~ lesson/week11
  huahua_trade_schema_show_create.sql  # MySQL 主库建表脚本（huahua_trade）
  CODE_WIKI.md                   # 本文档（仓库总览）
  python_file_index.md           # Python 文件索引（辅助快速定位）
  generate_python_file_index.py  # 生成索引的脚本
  _generate_py_html_docs.py      # 生成文档的脚本（仓库自带）
  CHANGELOG.md                   # 变更记录
  vercel.json                    # 部署配置
```

相关说明：

- 仓库顶层 README：[README.md](./README.md)
- Charles Wiki：[charles/CODE_WIKI.md](./charles/CODE_WIKI.md)
- Zoe Wiki：[zoe/CODE_WIKI.md](./zoe/CODE_WIKI.md)
- CEO 控制台说明：[ceo/README.md](./ceo/README.md)
- Charles 项目说明与启动：[charles/README.md](./charles/README.md)
- Zoe 项目说明与启动：[zoe/README.md](./zoe/README.md)

---

## 2. 整体架构（跨项目视角）

### 2.1 数据流（核心主线）

1. **数据源**：QMT / Tushare / AkShare / 研报文件 / 联网搜索（催化剂）等
2. **Charles（输入端）**：
   - 拉取/清洗数据，落库到 MySQL（`huahua_trade`）
   - 按任务域调度（cron）并记录运行结果
   - 提供数据浏览/导出、舆情监控、研报生成与助手 API
3. **Zoe（分析端）**：
   - 从 MySQL 读取行情/财务/宏观等，计算指标与信号
   - 主力识别与绩效分析（用于解释策略表现与交易质量）
4. **Ethan（执行端）**：
   - 连接 miniQMT/QMT，基于任务执行下单与执行监控
   - 提供执行任务 API 与 WebSocket 事件流（实时进度与审计）
5. **Kris（风控端）**：
   - 对交易请求做审批/限仓/止损/宏观门控，并记录审计日志
6. **CEO 控制台（整合端）**：
   - 提供统一 Web 工作台：实盘/模拟盘、回测、晨会、投研对话与调度器

### 2.2 依赖关系（项目之间）

- Charles、Zoe、CEO（晨会/龙头/回测相关）等模块 **共享同一套 MySQL 库**（`huahua_trade`），表结构主要由：
  - [huahua_trade_schema_show_create.sql](./huahua_trade_schema_show_create.sql) 提供基础表（行情/财务/宏观/新闻等）
  - Charles 后端启动时会自动补齐一些业务表（见下文 3.3）
- `lesson/` 中部分脚本同样会读写 `huahua_trade`（取决于具体 CASE）。
- CEO 的投研对话依赖 `ceo/third_party/charles_bundle` 中的 Charles/Nanobot 组件（见 `ceo/README.md`）。

---

## 3. Charles（数字员工情报官）

### 3.1 定位与职责

Charles 是“AI 量化交易系统输入端（Input）”：

- 对接数据源（QMT / AkShare / Tushare 等）
- 清洗与标准化后写入 MySQL（`huahua_trade`）
- 通过 API 暴露任务运行、数据浏览、导出交付、自选股等能力
- 提供 Web 控制台用于日常操作与可视化

项目说明与启动方式详见：[charles/README.md](./charles/README.md)

### 3.2 后端（FastAPI）架构

#### 入口与运行方式

- 开发启动入口：[charles/api/run_server.py](./charles/api/run_server.py)
  - 通过 `uvicorn` 运行 `charles_api.app:app`
- FastAPI 应用定义：[charles/api/charles_api/app.py](./charles/api/charles_api/app.py)
  - `create_app()` 初始化应用与路由聚合，模块末尾导出 `app = create_app()`

#### 模块划分（职责）

- API 应用与路由聚合：[charles/api/charles_api/app.py](./charles/api/charles_api/app.py)
  - 包含：健康检查、汇总、任务触发、任务计划、数据查询、导出、自选股、个股快照、研报/舆情/助手等路由
- 配置加载（.env）：[charles/api/charles_api/config.py](./charles/api/charles_api/config.py)
  - `load_settings()` 负责读取环境变量与默认值
- MySQL 访问封装：[charles/api/charles_api/db.py](./charles/api/charles_api/db.py)
  - `connect/query_dict/execute/executemany` 等函数统一 SQL 调用方式
- 任务域模型与请求体定义：[charles/api/charles_api/models.py](./charles/api/charles_api/models.py)
  - `JobDomain`：任务分域枚举（stock_daily/stock_financial/stock_news/...）
  - `JobRunRequest`：触发任务请求体
  - `JobRunResult`：任务执行结果结构（包含最终数据源与 fallback 链）
- 任务运行记录落盘：[charles/api/charles_api/job_store.py](./charles/api/charles_api/job_store.py)
  - 将每次任务执行状态写入 JSON（默认目录：`.charles/job_runs/`），供 Web 展示
- 任务实现（按域拆分）：[charles/api/charles_api/jobs/](./charles/api/charles_api/jobs/)
  - `stock_daily.py`：日线（含指标字段）入库
  - `stock_financial.py`：财务数据入库
  - `stock_news.py`：新闻/公告/研报抓取与可选 LLM 摘要
  - `sentiment_monitor.py`：舆情监控任务（落盘运行结果与详情）
  - `macro_indicator.py`、`rate_daily.py`、`calendar.py`、`report_consensus.py`、`catalyst.py`：宏观/利率/日历/研报一致预期/催化剂等
- 清洗逻辑：[charles/api/charles_api/cleaning/](./charles/api/charles_api/cleaning/)
  - 例如 `ohlcv.py`：OHLCV 字段清洗、对齐与标准化
- 研报生成模块：[charles/api/charles_api/reports/](./charles/api/charles_api/reports/)
- 舆情分析模块：[charles/api/charles_api/sentiment/](./charles/api/charles_api/sentiment/)
- 助手模块：[charles/api/charles_api/assistant/](./charles/api/charles_api/assistant/)

#### 关键流程（后端核心机制）

1. **应用启动初始化**
   - `create_app()` 读取配置并初始化 CORS
   - 自动确保以下业务表存在（通过 `CREATE TABLE IF NOT EXISTS`）：
     - `trade_stock_master`：股票代码与名称主表（用于补齐与搜索）
     - `trade_watchlist`：自选股（支持置顶与排序）
     - `trade_job_schedule`：任务定时调度配置（cron + enabled + params）
   - 为每个 `JobDomain` 创建线程锁，避免同域任务并发重入
   - 如 APScheduler 可用：加载 `trade_job_schedule` 并在进程内注册定时任务

2. **任务触发与执行**
   - API 发起运行请求（例如 `/api/jobs/run`），后端分发到对应的 `jobs/*.py`
   - 执行过程中持续更新 `JobRunResult` 并写入 `job_store`（JSON 文件）
   - 执行结果包含：
     - `dataSourceFinal`：最终使用的数据源
     - `fallbackChain`：数据源降级链路（见 Charles README 的“数据源优先级规则”）
     - `rowsWritten/itemsProcessed/failedItems`：入库与失败统计

3. **数据查询与交付**
   - 对外提供数据浏览接口（按 dataset 参数映射表/查询）
   - 支持导出 CSV/JSON（流式下载）

### 3.3 数据库与表（Charles 相关）

基础表结构来自：[huahua_trade_schema_show_create.sql](./huahua_trade_schema_show_create.sql)。

其中与 Charles 直接相关且最常用的表包括：

- `trade_stock_daily`：日线 OHLCV + 多个常用技术指标字段（MA/RSI/MACD/BOLL/KDJ 等）
- `trade_stock_financial`：季度财务（ROE/ROA/利润率/负债率等）
- `trade_stock_news`：新闻/公告/研报等文本数据（可包含摘要与情绪）
- `trade_macro_indicator` / `trade_rate_daily` / `trade_calendar_event`：宏观、利率、财经日历
- `trade_report_consensus`：研报一致预期

Charles 后端启动时自动创建（不在 SQL 主脚本中）：

- `trade_stock_master`
- `trade_watchlist`
- `trade_job_schedule`

### 3.4 前端（React Web 控制台）架构

#### 入口与路由

- Vite/React 入口：[charles/web/src/main.tsx](./charles/web/src/main.tsx)
- 应用与路由聚合：[charles/web/src/App.tsx](./charles/web/src/App.tsx)
- 页面模块：[charles/web/src/pages/](./charles/web/src/pages/)
  - `Dashboard`：总览（数据最新日期、最近任务等）
  - `Jobs`：采集任务触发、运行记录查看
  - `Data`：数据浏览与导出
  - `Watchlist` + `StockDetail`：自选股与个股详情

#### API Client

- 接口类型定义：[charles/web/src/api/types.ts](./charles/web/src/api/types.ts)
- 请求封装：[charles/web/src/api/client.ts](./charles/web/src/api/client.ts)

#### Dev 代理与运行方式

- Vite 代理配置：`/api -> http://localhost:8000/api`，见 [charles/web/vite.config.ts](./charles/web/vite.config.ts)

### 3.5 依赖（Charles）

- 后端依赖：[charles/api/requirements.txt](./charles/api/requirements.txt)
  - `fastapi` / `uvicorn` / `pymysql` / `pandas` / `akshare` / `tushare` / `openai` / `APScheduler` 等
- 前端依赖：[charles/web/package.json](./charles/web/package.json)
  - `react` / `react-router-dom` / `echarts` / `zustand` / `tailwindcss` / `vite` / `vitest` / `playwright` 等

### 3.6 运行方式（Charles）

以 Windows 开发环境为例（仓库文档已给出 PowerShell/cmd 方式），完整步骤见：[charles/README.md](./charles/README.md)。

- MySQL 初始化：
  - 执行 [huahua_trade_schema_show_create.sql](./huahua_trade_schema_show_create.sql)
  - 执行 [charles/sql/huahua_trade_charles_extra.sql](./charles/sql/huahua_trade_charles_extra.sql)
- 后端启动（仓库根目录）：
  - 安装依赖：`pip install -r api/requirements.txt`
  - 运行：`python api/run_server.py`（默认 `http://localhost:8000`）
- 前端启动：
  - `cd web && npm install && npm run dev`（默认 `http://localhost:5173`）
- 一键启动（开发）：
  - `charles/scripts/start_all.cmd` 或 `start_all.ps1`

---

## 4. Zoe（数字员工分析师）

### 4.1 定位与职责

Zoe 是“策略计算与因子挖掘端（Analysis）”，核心特点：

- 从 MySQL 读取行情/财务数据
- 计算技术指标（优先 TA-Lib，必要时退化为纯 Pandas 实现）
- 生成交易信号、评分与原因
- 选股（财务阈值 + 多因子打分）
- 回测（可选 backtrader）
- 自带 Web 控制台（Jinja2 模板，无需 Node）

项目说明与启动方式详见：[zoe/README.md](./zoe/README.md)

### 4.2 服务架构

#### 入口与路由

- 应用入口：[zoe/zoe/app/main.py](./zoe/zoe/app/main.py)
  - Web 页面：`/`、`/signals`、`/screener`、`/strategies`、`/backtest`
  - API：`/api/v1/technical/*`、`/api/v1/signals`、`/api/v1/screener/*`、`/api/v1/strategies`、`/api/v1/backtest/*` 等

#### 模块划分（职责）

- 配置加载：[zoe/zoe/app/config.py](./zoe/zoe/app/config.py)
- MySQL 访问：[zoe/zoe/app/db.py](./zoe/zoe/app/db.py)
- 行情/财务数据读取：[zoe/zoe/app/market_data.py](./zoe/zoe/app/market_data.py)
  - 将 `trade_stock_daily` 等表读取为 DataFrame
- 技术指标计算：
  - 主实现：[zoe/zoe/app/indicators.py](./zoe/zoe/app/indicators.py)
  - TA-Lib fallback：[zoe/zoe/app/_talib_fallback.py](./zoe/zoe/app/_talib_fallback.py)
- 信号生成：[zoe/zoe/app/signals.py](./zoe/zoe/app/signals.py)
- 财务筛选与多因子评分：[zoe/zoe/app/screener.py](./zoe/zoe/app/screener.py)
- 策略注册表（策略元信息与工厂）：[zoe/zoe/app/strategy_registry.py](./zoe/zoe/app/strategy_registry.py)
- 回测相关：
  - 回测 API 由 [main.py](./zoe/zoe/app/main.py) 中 `/api/v1/backtest/*` 实现
  - backtrader 作为可选依赖（未安装时会提示缺依赖）
- 主力识别模块：`zoe/zoe/app/mainforce/`
- 绩效分析模块：`zoe/zoe/app/performance/`

### 4.3 关键函数/类（Zoe）

- 指标计算入口：`add_technical_indicators(df)`
  - 位置：[zoe/zoe/app/indicators.py](./zoe/zoe/app/indicators.py)
  - 输出 MA/MACD/RSI/BOLL 等统一列，供信号/回测/图表复用
- 信号生成入口：`generate_signals(df)`
  - 位置：[zoe/zoe/app/signals.py](./zoe/zoe/app/signals.py)
  - 返回包含 `signal/score/reasons/snapshot` 的结构化结果
- 策略注册表：`get_strategy_registry()`
  - 位置：[zoe/zoe/app/strategy_registry.py](./zoe/zoe/app/strategy_registry.py)
  - 将策略以 “id -> 元信息 + 工厂函数” 的形式集中管理，供 UI/回测动态枚举与加载

### 4.4 依赖（Zoe）

- 基础依赖：[zoe/requirements.txt](./zoe/requirements.txt)
- 可选依赖：
  - TA-Lib：[zoe/requirements-talib.txt](./zoe/requirements-talib.txt)
  - 回测 backtrader：[zoe/requirements-backtest.txt](./zoe/requirements-backtest.txt)

### 4.5 运行方式（Zoe）

完整步骤见：[zoe/README.md](./zoe/README.md)。

- 配置：复制 `.env.example -> .env`，保证可连接 MySQL（`huahua_trade`）
- 安装依赖：`pip install -r requirements.txt`
- 启动：`python -m zoe.app.main`
  - Web 控制台：`http://127.0.0.1:8010/`
  - 健康检查：`http://127.0.0.1:8010/health`

---

## 5. Ethan（交易官）

Ethan 是交易执行与任务编排服务（FastAPI + WebSocket），核心能力包括：

- QMT 连接与交易查询（资产/持仓/订单/成交/事件）
- 交易执行任务创建、模拟与执行（带执行过程事件流）
- RL 训练与回测接口（训练过程通过 WS 推送）

入口与代码位置：

- 后端：`ethan/backend/`（启动入口：[run_server.py](./ethan/backend/run_server.py)）
- 后端 FastAPI：`ethan/backend/ethan_api/app.py`
- 前端：`ethan/frontend/`（Vite）

常用运行方式（默认端口 8001）：

```bash
python ethan/backend/run_server.py
```

依赖要点：

- 交易连接需要环境变量：`QMT_PATH`、`ACCOUNT_ID`（见 `POST /api/trading/connect`）
- 前端通过 CORS 允许来源：`ETHAN_CORS_ORIGINS`（默认 `http://localhost:5173`）

---

## 6. Kris（风控官）

Kris 是风控决策服务（FastAPI），核心能力包括：

- 交易请求审批：给出 `APPROVE/WARN/REJECT` 与原因，并可返回建议降仓金额/数量
- ATR 止损检查、持仓注册与移除
- 宏观门控（例如 VIX 风险系数）
- 审计日志与状态查询

入口与代码位置：

- 后端：`kris/api/`（启动入口：[run_server.py](./kris/api/run_server.py)，默认端口 8011）
- 风控引擎：`kris/api/kirs_api/risk_engine.py`
- Web：`kris/web/`（Vite）

---

## 7. CEO 控制台（整合型 Web 工作台）

CEO 控制台是整合型 Web 工作台（FastAPI + 模板页 + 可挂载 Gradio 投研对话），核心能力包括：

- 实盘/模拟盘监控与引擎启停
- 回测（单股/策略）
- 晨会工作流（LangGraph）
- 投研对话（依赖 `third_party/charles_bundle` 与 `DASHSCOPE_API_KEY`）
- 定时调度器（08:30 数据增量、交易时段启停等）

说明与启动见：[ceo/README.md](./ceo/README.md)

入口：

- Web：`python ceo/app.py`（默认 7865）
- Scheduler：`python ceo/scheduler.py`

---

## 8. lesson/（课程周代码）

课程周代码已统一迁移到 `lesson/`，按 `week1` ~ `week11` 组织。大多数文件是独立脚本，通常直接运行：

```bash
python your_script.py
```

其中部分 CASE 会读写 `huahua_trade`（需要先按建表 SQL 初始化数据库）。

---

## 9. 常用运行/开发清单（汇总）

### 9.1 MySQL（共享底座）

- 建库建表：[huahua_trade_schema_show_create.sql](./huahua_trade_schema_show_create.sql)
- Charles 扩展 SQL：[charles/sql/huahua_trade_charles_extra.sql](./charles/sql/huahua_trade_charles_extra.sql)

### 9.2 Charles

- 后端：`python charles/api/run_server.py`
- 前端：`cd charles/web && npm run dev`

### 9.3 Zoe

- `python -m zoe.app.main`

### 9.4 Ethan

- `python ethan/backend/run_server.py`

### 9.5 Kris

- `python kris/api/run_server.py`

### 9.6 CEO 控制台

- `python ceo/app.py`

---

## 10. 代码阅读建议（上手路径）

如果目标是快速理解“落地系统如何协同工作”，推荐阅读顺序：

1. [README.md](./README.md)（最新目录导航）
2. [CODE_WIKI.md](./CODE_WIKI.md)（系统总览与各模块关系）
3. Charles（输入端）：
   - [charles/CODE_WIKI.md](./charles/CODE_WIKI.md)
   - [charles/api/charles_api/app.py](./charles/api/charles_api/app.py)
4. MySQL 表结构（理解数据落在哪里）：[huahua_trade_schema_show_create.sql](./huahua_trade_schema_show_create.sql)
5. Zoe（分析端）：
   - [zoe/CODE_WIKI.md](./zoe/CODE_WIKI.md)
   - [zoe/zoe/app/main.py](./zoe/zoe/app/main.py)
6. Ethan（执行端）：[ethan/backend/ethan_api/app.py](./ethan/backend/ethan_api/app.py)
7. Kris（风控端）：[kris/api/kirs_api/app.py](./kris/api/kirs_api/app.py)
8. CEO 控制台（整合端）：[ceo/README.md](./ceo/README.md) 与 [ceo/app.py](./ceo/app.py)
9. 课程代码：需要追溯课堂实现时再从 `lesson/` 按周定位（可用 [python_file_index.md](./python_file_index.md) 辅助检索）
