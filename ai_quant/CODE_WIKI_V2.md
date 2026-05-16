# AI Quant 统一量化系统 - Code Wiki V2

## 项目概述

AI Quant 是一个统一的 AI 量化交易系统，整合了多个专业 AI Agent（Charles、Zoe、Ethan、Kris、CEO）协同工作，提供数据采集、技术分析、信号生成、交易执行、风险管理和智能研报生成的完整量化交易能力。项目采用前后端分离架构，后端基于 FastAPI，前端基于 React + TypeScript + Vite，同时集成 Streamlit AI 对话界面。

### 核心功能模块

| 模块 | 功能描述 | 技术实现 |
|------|---------|---------|
| 数据采集 | 从 MySQL 数据库采集股票日线、财务数据、新闻、宏观指标等 | PyMySQL + 批量调度 |
| 技术分析 | RSI、MACD、KDJ、布林带等技术指标计算 | Zoe Service + TA-Lib 脚本 |
| 智能研报 | 基于 RAG + FAISS 向量检索与 LLM 生成结构化研报 | LangChain + SQLite + FAISS + DashScope/DeepSeek |
| 晨会简报 | 每日自动聚合市场数据，进行板块轮动分析与选股 | LangGraph 工作流编排 |
| 交易执行 | 策略执行任务管理与 MiniQMT 网关代理 | FastAPI + 子进程脚本 |
| 风控审批 | 多层级风控规则检查与审计日志 | Kris RiskManager |
| AI 对话 | 自然语言量化交互入口，支持工具调用 | DeepAgent Engine + LangChain |
| 交易工作流 | Charles(投研) -> Zoe(信号) -> Kris(风控) -> Human(审批) -> Trader(下单) | LangGraph StateGraph |

### 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 后端 API | FastAPI + Pydantic v2 | 高性能异步 API 服务 |
| 前端 | React 18 + TypeScript + Vite 6 | 现代化 React 应用 |
| UI 框架 | TailwindCSS 3 + clsx + tailwind-merge | 原子化 CSS |
| 状态管理 | Zustand 5 | 轻量级状态管理 |
| 图表 | ECharts + echarts-for-react | 金融数据可视化 |
| AI 框架 | LangGraph 0.4 | Agent 工作流编排 |
| 数据库 | MySQL (腾讯云 CDB) | 主数据存储 |
| 向量检索 | FAISS + SQLite | RAG 向量索引 |
| LLM 模型 | DashScope(通义千问) / DeepSeek | 研报生成与对话 |
| ASGI 服务器 | Uvicorn 0.34 | 高性能 ASGI 服务 |

---

## 项目架构

### 整体架构图

```
用户请求 (React Frontend / API Client)
    |
    v
FastAPI Application (backend/app.py)
    |
    +-- Middleware: CORS / Rate Limit / API Key Guard / HTTP Access Log
    |
    +-- API Routers (/api/v1/*)
    |     +-- health / summary / data / watchlist / jobs
    |     +-- reports / analysis / sentiment / execution
    |     +-- trading / risk / console / agent / conversation
    |
    +-- Agent Layer (agents/)
    |     +-- Router Agent (意图路由)
    |     +-- Quant Team Agent (量化助手)
    |     +-- Report Agent (研报生成)
    |     +-- Deep Agent (通用智能体)
    |
    +-- Workflow Layer (workflow/)
    |     +-- Trading Team Graph (LangGraph)
    |     |     Charles -> Zoe -> Kris -> Human -> Trader
    |     +-- Morning Brief Graph (LangGraph)
    |     |     Collect -> Run
    |
    +-- Core Services (core/)
    |     +-- analysis (技术分析 & 信号生成)
    |     +-- execution (执行任务管理)
    |     +-- console/morning_brief (晨会简报)
    |     +-- risk (风控审批 & 审计)
    |     +-- jobs (数据采集调度)
    |     +-- db (MySQL 连接管理)
    |
    +-- Infrastructure (infra/)
    |     +-- reports/rag (RAG 向量检索)
    |     +-- storage/report_store (报告任务持久化)
    |     +-- storage/job_store (Agent 运行记录)
    |     +-- storage/logging_service (统一日志服务)
    |     +-- qmt_gateway_client (QMT 网关客户端)
    |
    +-- LLM Engine (llm/)
          +-- deepagent_engine (DeepAgent 引擎)
          +-- clients/deepseek_client (DeepSeek 客户端)
          +-- skills/* (LLM 技能脚本)
          +-- tools/* (工具定义与执行)

外部依赖:
    MySQL (腾讯云 huahua_trade)
    QMT Gateway (MiniQMT 代理服务)
    DashScope API / DeepSeek API
    FAISS + SQLite (RAG 本地索引)
```

### 数据流向 — 交易工作流

```
用户指定标的和资金
    |
    v
Charles Node (投研情报官)
    |-- web_search: 联网搜索基本面、行业动态
    |-- stock_price: 获取实时K线数据
    |-- financial_analysis: 财务比率分析
    |-- 输出: InvestmentView(stance, confidence, summary, catalysts, risks)
    |
    v
Zoe Node (信号官)
    |-- strategy-backtest: 运行 MACD 策略回测
    |-- 结合 Charles 观点判断方向与仓位
    |-- 输出: TradeSignal(direction, quantity, price, reason)
    |
    v
Kris Node (风控官)
    |-- 黑名单检查 / 资金限制 / ATR 波动率检查
    |-- 输出: RiskVerdict(decision, reason, suggested_max_pct)
    |
    v
Human Node (人在回路)
    |-- 展示交易信号与风控结论
    |-- 自动模式默认批准
    |-- 输出: approved(boolean)
    |
    v
Trader Node (交易执行)
    |-- dry-run 模式(默认) / 真实下单
    |-- 输出: TradeResult(order_id, submitted_at)
    |
    v
END
```

### 数据流向 — 晨会简报

```
用户触发晨会请求
    |
    v
Router Agent (路由)
    |-- 识别"晨会"关键词
    |-- 路由到 morning_brief_graph
    |
    v
Collect Node (参数初始化)
    |-- 设置行业层级、回溯天数、采样数等默认参数
    |
    v
Run Node (执行晨会分析)
    |-- 1. list_sectors: 从 MySQL 获取板块列表
    |-- 2. load_sector_kline: 获取板块K线数据
    |-- 3. _calc_derivatives: 计算 ROC/MA/MACD 等衍生指标
    |-- 4. detect_phase: 判断板块所处阶段(主升/钝化/主跌/抄底)
    |-- 5. rank_industries_with_phase: z-score 综合打分排序
    |-- 6. pick_stocks_from_industries: 多因子选股
    |-- 7. build_report: 生成 Markdown + HTML 报告
    |
    v
END (返回报告)
```

---

## 目录结构

```
ai_quant/
├── backend/                          # 后端服务
│   ├── api/                          # API 路由层 (FastAPI Router)
│   │   ├── health.py                 # 健康检查
│   │   ├── summary.py                # 数据汇总
│   │   ├── data_charles.py           # 数据查询(多数据集分页)
│   │   ├── data_status.py            # 数据状态
│   │   ├── watchlist.py              # 自选股管理
│   │   ├── stock_detail.py           # 个股详情
│   │   ├── stock_select.py           # 选股策略
│   │   ├── jobs.py                   # 任务调度(JIRA Runner)
│   │   ├── reports.py                # 研报生成(任务管理)
│   │   ├── analysis_zoe.py           # 技术分析与信号
│   │   ├── sentiment.py              # 舆情与宏观
│   │   ├── execution_ethan.py        # 交易执行
│   │   ├── trading_qmt.py            # QMT 交易
│   │   ├── risk_kris.py              # 风险管理
│   │   ├── console_ceo.py            # CEO 控制台
│   │   ├── agent.py                  # AI Agent 入口
│   │   ├── conversation_api.py       # 对话会话管理
│   │   ├── logs.py                   # 日志查询
│   │   ├── approval.py              # 风控审批(旧版)
│   │   ├── approval_models.py        # 审批数据模型
│   │   ├── signals.py                # 信号接口
│   │   ├── sim_account.py            # 模拟账户
│   │   ├── performance.py            # 绩效分析
│   │   └── mainforce.py             # 主力资金识别
│   ├── agents/                       # AI Agent 实现
│   │   ├── router_agent.py           # 意图路由 Agent
│   │   ├── quant_team_agent.py       # 量化团队 Agent
│   │   ├── report_agent.py           # 研报生成 Agent(五步法)
│   │   └── deepagent_agent.py        # DeepAgent 封装
│   ├── workflow/                     # LangGraph 工作流
│   │   ├── trading_state.py          # 交易状态定义(TypedDict)
│   │   ├── trading_team_graph.py     # 交易团队工作流图
│   │   ├── morning_brief_graph.py    # 晨会简报工作流图
│   │   └── nodes/                    # 工作流节点
│   │       ├── charles_node.py       # 投研情报官节点
│   │       ├── zoe_node.py           # 信号官节点
│   │       ├── kris_node.py          # 风控官节点
│   │       ├── human_node.py         # 人工审批节点
│   │       └── trader_node.py        # 交易执行节点
│   ├── core/                         # 核心业务逻辑
│   │   ├── db.py                     # MySQL 连接管理 & CRUD
│   │   ├── analysis/                 # 技术分析模块
│   │   │   ├── service.py            # 信号/样本查询服务
│   │   │   └── tech_signals.py       # 技术指标计算
│   │   ├── execution/                # 执行模块
│   │   │   ├── models.py             # 执行任务 Pydantic 模型
│   │   │   ├── service.py            # 执行任务管理
│   │   │   └── store.py              # 内存存储(InMemoryStore)
│   │   ├── console/                  # 控制台模块
│   │   │   ├── morning_brief.py      # 晨会简报核心逻辑
│   │   │   └── service.py           # CEO 控制台服务
│   │   ├── jobs/                     # 数据采集任务
│   │   │   ├── runner.py             # 任务运行器(调度各domain)
│   │   │   ├── common.py             # JobStats 数据模型
│   │   │   └── domains/              # 各领域采集实现
│   │   │       ├── stock_daily.py     # 股票日线
│   │   │       ├── stock_financial.py # 财务数据
│   │   │       ├── stock_financial_qmt.py # QMT 财务数据
│   │   │       ├── stock_news.py     # 股票新闻
│   │   │       ├── macro_indicator.py # 宏观指标
│   │   │       ├── rate_daily.py     # 利率数据
│   │   │       ├── calendar.py       # 日历数据
│   │   │       ├── catalyst.py       # 催化剂事件
│   │   │       ├── report_consensus.py # 研报共识
│   │   │       ├── sentiment_monitor.py # 舆情监控
│   │   │       └── stock_sw_industry_simple.py # 申万行业分类
│   │   └── risk/                    # 风控模块
│   │       └── service.py            # RiskManager 风控审批
│   ├── infra/                        # 基础设施
│   │   ├── reports/                  # 研报基础设施
│   │   │   └── rag.py                # RAG 向量检索(FAISS+SQLite)
│   │   ├── storage/                  # 存储服务
│   │   │   ├── report_store.py       # 报告任务持久化
│   │   │   ├── job_store.py          # Agent 运行记录
│   │   │   └── logging_service.py    # 统一日志服务
│   │   └── qmt_gateway_client.py     # QMT 网关 HTTP 客户端
│   ├── llm/                          # LLM 相关
│   │   ├── deepagent_engine.py       # DeepAgent 对话引擎
│   │   ├── clients/                  # LLM 客户端
│   │   │   └── deepseek_client.py    # DeepSeek API 客户端
│   │   ├── skills/                   # LLM 技能目录
│   │   │   ├── write-report/         # 研报撰写(五步法)
│   │   │   ├── web-search-qwen/     # 联网搜索(通义)
│   │   │   ├── web-search-universal/ # 通用搜索
│   │   │   ├── read-pdf/            # PDF 解析与查询
│   │   │   ├── stock-price/         # 股票行情
│   │   │   ├── financial-analysis/   # 财务分析
│   │   │   ├── compare-reports/      # 报告对比
│   │   │   ├── sentiment-analysis/   # 舆情情绪分析
│   │   │   ├── strategy-backtest/    # 策略回测
│   │   │   ├── strategy-recommend/   # 策略推荐
│   │   │   ├── trade-order/          # 交易下单
│   │   │   ├── miniqmt-kline/       # MiniQMT K线
│   │   │   ├── talib/               # TA-Lib 指标
│   │   │   ├── backtrader/          # Backtrader 回测
│   │   │   ├── bond-credit-review/   # 债券信用评审
│   │   │   ├── blog-post/           # 博客文章
│   │   │   ├── investment-research/  # 投资研究
│   │   │   ├── query-writing/       # 查询编写
│   │   │   ├── schema-exploration/   # 模式探索
│   │   │   └── biz-skill-creator/   # 业务技能创建器
│   │   └── tools/                    # 工具定义
│   │       └── tools/                # 工具函数(__init__.py)
│   ├── models/                       # 数据模型
│   │   └── models/__init__.py
│   ├── common/                       # 公共模块
│   │   ├── response.py               # 统一响应格式(ok/fail)
│   │   ├── pagination.py             # 分页标准化
│   │   └── errors.py                 # ApiError 异常类
│   ├── migrations/                   # 数据库迁移脚本
│   │   ├── 002_expanded_schema.sql
│   │   ├── 003_add_created_at_field.sql
│   │   ├── 004_add_pe_pb_market_cap.sql
│   │   ├── 005_add_sim_account.sql
│   │   ├── 005_add_sw_industry.sql
│   │   ├── 005_add_sw_industry_simple.sql
│   │   ├── 005_create_performance_tables.sql
│   │   ├── 006_add_sim_indexes.sql
│   │   ├── 006_create_signal_tables.sql
│   │   ├── 006_risk_management.sql
│   │   ├── 006_risk_management_sqlite.sql
│   │   ├── 007_risk_management_extended.sql
│   │   ├── 007_sentiment_monitor.sql
│   │   ├── 008_add_performance_fields.sql
│   │   ├── 008_create_signal_tables.sqlite.sql
│   │   ├── 009_mainforce_identification.sql
│   │   ├── 009_mainforce_identification_final.sql
│   │   ├── 009_mainforce_identification_simple.sql
│   │   ├── 009_mainforce_identification_sqlite.sql
│   │   └── add_watchlist_groups.sql
│   ├── scripts/                      # 工具脚本
│   │   └── report_tasks_cli.py       # 研报任务 CLI
│   ├── tests/                        # 测试
│   │   ├── test_api_smoke.py
│   │   ├── test_bugfix_regressions.py
│   │   ├── test_ethan_embedded.py
│   │   ├── test_logging_service.py
│   │   ├── test_morning_brief_embedded.py
│   │   ├── test_mysql_config.py
│   │   ├── test_qmt_gateway_proxy.py
│   │   ├── test_reports_api.py
│   │   ├── test_reports_rag.py
│   │   └── test_zoe_signals_logic.py
│   ├── migrations_sqlite.py          # SQLite 迁移脚本
│   ├── app.py                        # FastAPI 应用工厂
│   ├── config.py                     # Settings 配置管理
│   ├── run_server.py                 # 服务启动入口
│   └── pytest.ini                    # Pytest 配置
├── web/                              # React 前端
│   ├── src/
│   │   ├── App.tsx                   # React Router 路由配置
│   │   ├── main.tsx                  # 应用入口
│   │   ├── index.css                 # 全局样式(Tailwind)
│   │   ├── api/                      # API 客户端层
│   │   │   ├── client.ts             # HTTP 请求封装(fetchJson/postJson)
│   │   │   ├── types.ts              # TypeScript 类型定义
│   │   │   ├── approval.ts           # 审批 API
│   │   │   └── mainforce.ts          # 主力资金 API
│   │   ├── components/               # 通用 UI 组件
│   │   │   ├── AppShell.tsx          # 应用外壳(侧边栏+顶栏)
│   │   │   ├── AssistantDrawer.tsx   # AI 助手抽屉
│   │   │   ├── Badge.tsx             # 徽章组件
│   │   │   ├── Button.tsx            # 按钮组件
│   │   │   ├── Card.tsx              # 卡片组件
│   │   │   ├── Empty.tsx             # 空状态组件
│   │   │   ├── ErrorBoundary.tsx     # 错误边界
│   │   │   ├── StatusBadge.tsx       # 状态徽章
│   │   │   ├── StockPicker.tsx       # 股票选择器
│   │   │   ├── Tabs.tsx              # 标签页组件
│   │   │   └── Toast.tsx             # 吐司通知
│   │   ├── pages/                    # 页面组件
│   │   │   ├── Home.tsx              # 首页
│   │   │   ├── Dashboard.tsx         # 仪表盘
│   │   │   ├── InfoAccess.tsx        # 信息获取(父页面)
│   │   │   ├── Jobs.tsx              # 数据采集任务
│   │   │   ├── JobDetail.tsx         # 任务详情
│   │   │   ├── WatchSentiment.tsx    # 舆情监控
│   │   │   ├── MacroData.tsx         # 宏观数据
│   │   │   ├── FinancialHot.tsx      # 财经热点
│   │   │   ├── DataDelivery.tsx      # 数据投送
│   │   │   ├── Watchlist.tsx         # 自选股
│   │   │   ├── Reports.tsx           # 研报中心
│   │   │   ├── StockDetail.tsx       # 个股详情
│   │   │   ├── Execution.tsx         # 执行监控(父页面)
│   │   │   ├── ExecutionTasks.tsx    # 执行任务列表
│   │   │   ├── ExecutionPositions.tsx # 持仓查询
│   │   │   ├── ExecutionRecords.tsx  # 成交记录
│   │   │   ├── Risk.tsx              # 风险管理(父页面)
│   │   │   ├── RiskApprove.tsx       # 风控审批
│   │   │   ├── RiskRules.tsx         # 风控规则
│   │   │   ├── RiskAudit.tsx         # 风控审计
│   │   │   ├── StrategyAnalysis.tsx  # 策略分析(父页面)
│   │   │   ├── StrategyLibrary.tsx   # 策略库
│   │   │   ├── StrategyInstances.tsx # 策略实例
│   │   │   ├── StrategyBacktest.tsx  # 策略回测
│   │   │   ├── StockSelect.tsx       # 选股(父页面)
│   │   │   ├── StockSelectFundamental.tsx # 基本面选股
│   │   │   ├── StockSelectFactor.tsx # 因子选股
│   │   │   ├── StockSelectML.tsx     # ML选股
│   │   │   ├── Opportunity.tsx       # 机会挖掘(父页面)
│   │   │   ├── OpportunityUnusual.tsx # 异常机会
│   │   │   ├── OpportunityLimitUp.tsx # 涨停机会
│   │   │   ├── OpportunitySector.tsx # 板块机会
│   │   │   ├── MainForceIdentification.tsx # 主力识别
│   │   │   ├── WorkFlow.tsx          # 工作流(父页面)
│   │   │   ├── WorkFlowTeam.tsx      # 团队交易工作流
│   │   │   ├── WorkFlowMorning.tsx   # 晨会工作流
│   │   │   ├── WorkFlowDragon.tsx    # 多空线工作流
│   │   │   └── NotFound.tsx          # 404 页面
│   │   ├── hooks/
│   │   │   └── useTheme.ts           # 主题 Hook
│   │   └── lib/
│   │       └── utils.ts              # 工具函数
│   ├── e2e/                          # E2E 测试
│   │   ├── basic.spec.ts
│   │   ├── full_system_test.spec.ts
│   │   ├── report_e2e_tests.spec.ts
│   │   ├── trading_api.spec.ts
│   │   └── api_test_runner.py
│   ├── package.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   ├── tsconfig.json
│   └── tailwind.config.js
├── docs/                             # 文档
│   ├── PRD.md                        # 产品需求文档
│   ├── USER_GUIDE.md                 # 用户使用指南
│   ├── AI_QUANT_LOGGING_SYSTEM_DESIGN.md # 日志系统设计
│   ├── diagrams/                     # 架构图 (PlantUML/drawio)
│   └── screenshots/                  # 系统截图
├── .env                              # 环境变量配置
├── .dockerignore
├── CODE_WIKI_V2.md                   # 本文档
├── README.md                         # 项目 README
└── backup/                           # 备份
```

---

## 后端模块详解

### 1. 应用入口 (app.py)

**文件位置**: [backend/app.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/app.py)

FastAPI 应用工厂函数 `create_app()`，完成以下初始化：

- 初始化日志系统 (`init_logging()`)
- 加载应用配置 (`config.get_settings()`)
- 配置 CORS 中间件 (禁止通配符)
- 配置速率限制中间件 (基于 IP，默认 10 秒内最多 200 次)
- 配置 API 密钥认证中间件
- 配置 HTTP 访问日志中间件
- 注册所有业务路由（17 个 Router）
- 启动时: 初始化任务调度器 + 速率限制状态清理
- 关闭时: 关闭任务调度器 + 关闭日志系统

**注册的路由列表**:

| 前缀 | Router | 功能 |
|------|--------|------|
| `/api/v1/health` | health_router | 健康检查 |
| `/api/v1/summary` | summary_router | 数据汇总 |
| `/api/v1/data-status` | data_status_router | 数据状态 |
| `/api/v1/data` | data_router | 数据查询 |
| `/api/v1/watchlist` | watchlist_router | 自选股 |
| `/api/v1/stock-detail` | stock_detail_router | 个股详情 |
| `/api/v1/stock-select` | stock_select_router | 选股 |
| `/api/v1/jobs` | jobs_router | 任务调度 |
| `/api/v1/reports` | reports_router | 研报生成 |
| `/api/v1/analysis` | analysis_router | 技术分析 |
| `/api/v1/sentiment` | sentiment_router | 舆情宏观 |
| `/api/v1/execution` | execution_router | 交易执行 |
| `/api/v1/trading` | trading_router | QMT 交易 |
| `/api/v1/risk` | risk_router | 风险管理 |
| `/api/v1/console` | console_router | CEO 控制台 |
| `/api/v1/logs` | logs_router | 日志查询 |
| `/api/v1/agent` | agent_router | AI 智能体 |
| `/api/v1/conversation` | conversation_router | 对话会话 |
| `/api/v1/approval` | approval_router | 旧版审批 |
| `/api/v1/mainforce` | mainforce_router | 主力资金 |
| `/api/v1/signals` | signals_router | 信号 |
| `/api/v1/sim-account` | sim_account_router | 模拟账户 |
| `/api/v1/performance` | performance_router | 绩效 |

### 2. 配置管理 (config.py)

**文件位置**: [backend/config.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/config.py)

使用 `frozen=True` 的 dataclass 确保配置不可变：

```python
@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Quant Unified API"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    api_key: str = ""

@dataclass(frozen=True)
class LoggingSettings:
    log_dir: Path          # 日志文件存储目录
    log_level: str         # 日志级别
    max_bytes: int         # 单文件最大字节数 (默认 10MB)
    backup_count: int      # 备份文件数
    console_enabled: bool  # 是否输出到控制台
    file_enabled: bool     # 是否输出到文件
```

**环境变量**:

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AI_QUANT_CORS_ORIGINS` | `http://localhost:5173` | CORS 来源(逗号分隔) |
| `AI_QUANT_API_KEY` | - | API 访问密钥 |
| `AI_QUANT_RATE_LIMIT_WINDOW_SECONDS` | `10` | 速率限制时间窗口(秒) |
| `AI_QUANT_RATE_LIMIT_MAX` | `200` | 速率限制最大请求数 |
| `AI_QUANT_LOG_DIR` | `.ai_quant/logs` | 日志目录 |
| `AI_QUANT_LOG_LEVEL` | `INFO` | 日志级别 |
| `AI_QUANT_LOG_MAX_BYTES` | `10485760` | 日志文件大小限制 |
| `AI_QUANT_LOG_BACKUP_COUNT` | `5` | 日志备份数 |
| `AI_QUANT_LOG_CONSOLE` | `true` | 控制台日志开关 |
| `AI_QUANT_LOG_FILE` | `true` | 文件日志开关 |
| `AI_QUANT_REPORT_USE_LLM` | `0` | 启用 LLM 研报 |
| `AI_QUANT_REPORT_TIMEOUT_SECONDS` | `300` | 研报超时(秒) |
| `AI_QUANT_REPORT_LLM_TIMEOUT_SECONDS` | `90` | LLM 超时(秒) |
| `AI_QUANT_REPORT_TASK_STORE_DIR` | `.ai_quant/report_tasks` | 报告任务存储目录 |
| `AI_QUANT_CHARLES_JOB_STORE_DIR` | - | Charles 任务存储目录 |
| `AI_QUANT_QMT_GATEWAY_BASE` | - | QMT 网关地址 |
| `AI_QUANT_QMT_GATEWAY_TOKEN` | - | QMT 网关 Token |
| `DASHSCOPE_API_KEY` | - | 通义千问 API Key |
| `DEEPSEEK_API_KEY` | - | DeepSeek API Key |

**数据库配置(支持三种格式)**:

| 格式前缀 | 示例 |
|---------|------|
| `WUCAI_SQL_*` | `WUCAI_SQL_HOST`, `WUCAI_SQL_PORT` |
| `DB_*` | `DB_HOST`, `DB_PORT` |
| `MYSQL_*` | `MYSQL_HOST`, `MYSQL_PORT` |

### 3. 数据库模块 (core/db.py)

**文件位置**: [backend/core/db.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/db.py)

基于 PyMySQL 的数据库操作层：

| 函数 | 功能 | 说明 |
|------|------|------|
| `load_mysql_config()` | 加载 MySQL 配置 | 从环境变量读取(支持3种命名格式) |
| `connect(cfg)` | 建立连接 | 自动提交 + DictCursor |
| `query_dict(conn, sql, params)` | 执行查询 | 参数化查询防 SQL 注入 |
| `execute(conn, sql, params)` | 执行写操作 | 返回影响行数 |
| `executemany(conn, sql, rows)` | 批量写入 | 提高大量插入效率 |

### 4. API 路由层

#### 4.1 数据查询 API (api/data_charles.py)

**文件位置**: [backend/api/data_charles.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/data_charles.py)

提供多数据集的分页查询与导出功能。

**支持的 datasets**: `trade_stock_daily`, `trade_stock_financial`, `trade_stock_news`, `trade_macro_indicator`, `trade_rate_daily`, `trade_report_consensus`, `trade_calendar_event`

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/v1/data/summary` | 数据源摘要 |
| GET | `/api/v1/data/{dataset}` | 分页查询(支持 stock_code/trade_date 过滤) |
| POST | `/api/v1/export` | 导出 CSV/JSON |

#### 4.2 技术分析 API (api/analysis_zoe.py)

**文件位置**: [backend/api/analysis_zoe.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/analysis_zoe.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/v1/analysis/status` | 分析服务状态 |
| GET | `/api/v1/analysis/stocks/sample` | 样本股票列表 |
| GET | `/api/v1/analysis/signals` | 股票技术信号 |

技术指标(由 `tech_signals.py` 计算): RSI6/12/24, MA5/10/20/60, MACD(DIF/DEA/BAR), 布林带, KDJ

#### 4.3 研报生成 API (api/reports.py)

**文件位置**: [backend/api/reports.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/reports.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/v1/reports/tasks` | 查询研报任务列表 |
| POST | `/api/v1/reports/tasks` | 创建研报任务 |
| DELETE | `/api/v1/reports/tasks/{task_id}` | 删除任务 |
| POST | `/api/v1/reports/tasks/{task_id}/retry` | 重试失败任务 |
| GET | `/api/v1/reports/tasks/{task_id}/view` | 查看研报内容 |
| GET | `/api/v1/reports/rag/status` | RAG 索引状态 |
| POST | `/api/v1/reports/rag/ingest` | 触发 RAG 索引构建 |
| GET | `/api/v1/reports/rag/query` | RAG 语义检索 |

**研报生成模式**: qwen(通义千问), qwen_with_rag(RAG 增强), deepseek_with_web(DeepSeek+联网)
**任务状态**: waiting -> running -> success/failed

#### 4.4 任务调度 API (api/jobs.py)

**文件位置**: [backend/api/jobs.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/jobs.py)

支持的 Job 域: `stock_daily`, `stock_financial`, `stock_news`, `macro_indicator`, `rate_daily`, `calendar`, `report_consensus`, `catalyst`, `sentiment_monitor`

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/v1/jobs/runs` | 任务运行记录 |
| POST | `/api/v1/jobs/runs` | 创建运行记录 |
| GET | `/api/v1/jobs/schedules` | 调度配置查询 |
| PUT | `/api/v1/jobs/schedules/{domain}` | 更新调度配置 |

#### 4.5 执行 API (api/execution_ethan.py)

**文件位置**: [backend/api/execution_ethan.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/execution_ethan.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/v1/execution/status` | 服务状态 |
| POST | `/api/v1/execution/tasks` | 创建执行任务 |
| GET | `/api/v1/execution/tasks` | 任务列表 |
| GET | `/api/v1/execution/tasks/{task_id}` | 任务详情 |

**执行策略**: twap(时间加权), vwap(量加权), rl(强化学习)
**任务状态**: draft -> running -> stopped/finished/failed

#### 4.6 风控 API (api/risk_kris.py)

**文件位置**: [backend/api/risk_kris.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/risk_kris.py)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/v1/risk/status` | 服务状态 |
| POST | `/api/v1/risk/approve` | 订单风控审批 |
| GET | `/api/v1/risk/audit` | 审计日志 |

**风控检查流程**: 总资产验证 -> 交易方向 -> 金额校验 -> ATR 波动率 -> 数量检查 -> 最终审批
**决策类型**: APPROVE(批准), WARN(警告), REJECT(拒绝)

#### 4.7 其他 API 端点

| 文件 | 前缀 | 主要功能 |
|------|------|---------|
| [api/sentiment.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/sentiment.py) | `/api/v1/sentiment` | 舆情监控与宏观指标 |
| [api/trading_qmt.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/trading_qmt.py) | `/api/v1/trading` | QMT 交易(连接/下单/撤单) |
| [api/watchlist.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/watchlist.py) | `/api/v1/watchlist` | 自选股 CRUD |
| [api/stock_detail.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/stock_detail.py) | `/api/v1/stock-detail` | 个股详情与行情 |
| [api/stock_select.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/stock_select.py) | `/api/v1/stock-select` | 选股策略(基本面/因子/ML) |
| [api/console_ceo.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/console_ceo.py) | `/api/v1/console` | CEO 控制台(系统总览/晨会触发) |
| [api/agent.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/agent.py) | `/api/v1/agent` | AI Agent 入口(运行/流式/工具) |
| [api/conversation_api.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/conversation_api.py) | `/api/v1/conversation` | 对话会话管理 |
| [api/logs.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/logs.py) | `/api/v1/logs` | 日志查询 |
| [api/mainforce.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/mainforce.py) | `/api/v1/mainforce` | 主力资金识别 |
| [api/signals.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/signals.py) | `/api/v1/signals` | 信号管理 |
| [api/sim_account.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/sim_account.py) | `/api/v1/sim-account` | 模拟账户 |
| [api/performance.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/performance.py) | `/api/v1/performance` | 绩效分析 |

---

### 5. Agent 模块

#### 5.1 路由 Agent (agents/router_agent.py)

**文件位置**: [backend/agents/router_agent.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/agents/router_agent.py)

根据用户输入进行关键词路由：

| 输入 | 路由目标 | 原因 |
|------|---------|------|
| 空/None | `none` | 空输入 |
| 包含"晨会" | `graph:morning_brief` | 关键词匹配 |
| 其他 | `tool:quant_assistant` | 默认路由 |

#### 5.2 量化团队 Agent (agents/quant_team_agent.py)

**文件位置**: [backend/agents/quant_team_agent.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/agents/quant_team_agent.py)

处理通用量化任务，根据用户输入中的关键词进行子模块路由：

| 关键词 | 路由模块 | 说明 |
|--------|---------|------|
| 数据/汇总/概览 | Charles | 数据查询 |
| 执行/下单/买入/卖出 | Ethan + Kris | 交易执行 |
| 风控/审批/风险 | Kris | 风控审批 |
| 报告/分析/个股 | Charles + Zoe | 分析报告 |

#### 5.3 研报 Agent (agents/report_agent.py)

**文件位置**: [backend/agents/report_agent.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/agents/report_agent.py)

基于国泰君安"五步法"方法论生成深度研报：

1. **信息差** — 市场还不知道/忽视了什么？
2. **逻辑差** — 市场的推理错在哪里？
3. **预期差** — 一致预期 vs 实际偏离多大？
4. **催化剂** — 什么事件会引爆重估？
5. **结论+风险闭环** — 最终判断 + 哪里可能出错？

**可用工具**: web_search, query_pdf(RAG), stock_price, financial_analysis, compare_reports, sentiment_analysis
**支持模型**: qwen-plus(默认), deepseek-chat
**迭代机制**: 多轮工具调用(默认最多4轮)收集信息后生成最终研报

#### 5.4 DeepAgent (agents/deepagent_agent.py + llm/deepagent_engine.py)

**文件位置**: [backend/agents/deepagent_agent.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/agents/deepagent_agent.py)

通用智能体引擎，支持：
- 多轮对话(基于 thread_id)
- 自动工具调用(从 tools 注册表加载)
- LangChain ChatTongyi 集成
- 对话历史管理(最多保留 20 条)

**可用工具**: web_search, get_kline(行情), run_backtest(回测), place_order(下单), query_account(账户)等

---

### 6. 工作流模块 (workflow/)

#### 6.1 交易团队工作流 (trading_team_graph.py)

**文件位置**: [backend/workflow/trading_team_graph.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/workflow/trading_team_graph.py)

基于 LangGraph StateGraph 的交易决策流水线：

```
START -> charles -> zoe -> kris -> (条件判断: 否决? -> zoe_retry/zoe | 通过? -> human)
                                          -> human -> (条件判断: 批准? -> trader | 否决? -> END)
                                                      -> trader -> END
```

**状态定义** ([trading_state.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/workflow/trading_state.py)):

| 字段 | 类型 | 所有权 | 说明 |
|------|------|--------|------|
| `investment_view` | `InvestmentView` | Charles | 投研观点(立场/信心/摘要/催化剂/风险) |
| `trade_signal` | `TradeSignal` | Zoe | 交易信号(方向/数量/价格/策略) |
| `risk_verdict` | `RiskVerdict` | Kris | 风控决议(决策/理由/建议仓位) |
| `approved` | `Optional[bool]` | Human | 人工审批结果 |
| `trade_result` | `TradeResult` | Trader | 下单回执 |
| `retry_count` | `int` | 公共 | 重试计数 |
| `messages` | `Annotated[list, add]` | 公共 | 审计消息列表 |

**重试机制**: 当 Kris 连续否决达到 `max_retry`(默认2) 上限时终止流程

#### 6.2 晨会简报工作流 (morning_brief_graph.py)

**文件位置**: [backend/workflow/morning_brief_graph.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/workflow/morning_brief_graph.py)

```
START -> collect(参数初始化) -> run(晨会分析) -> END
```

晨会核心分析流程 ([core/console/morning_brief.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/console/morning_brief.py)):

1. `normalize_params()` - 参数规范化
2. `list_sectors()` - 从 MySQL 加载板块列表
3. `load_sector_kline()` - 加载板块 K 线(close_idx/total_amount)
4. `_calc_strength_indicators()` - 强度指标(MOM_21/VOL_RATIO)
5. `_calc_derivatives()` - 衍生指标(ROC/MA_SLOPE/MACD_HIST)
6. `detect_phase()` - 拐点探测(主升加速/高位钝化/主跌/左侧抄底/中性)
7. `rank_industries_with_phase()` - Z-Score 综合打分排序
8. `pick_stocks_from_industries()` - 多因子选股(alpha打分)
9. `build_report()` - 生成 Markdown + HTML 报告

---

### 7. 核心业务模块

#### 7.1 技术分析 (core/analysis/)

- [service.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/analysis/service.py): 信号生成入口，从 MySQL 读取日线数据，调用 `tech_signals.generate_signals()`
- [tech_signals.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/analysis/tech_signals.py): 技术指标计算，含 RSI/MA/MACD/KDJ/布林带

#### 7.2 执行模块 (core/execution/)

- [models.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/execution/models.py): Pydantic 数据模型 (ExecutionTask/ExecutionConstraints/StrategyType)
- [service.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/execution/service.py): 任务 CRUD
- [store.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/execution/store.py): 线程安全的内存存储 (InMemoryStore)

#### 7.3 风控模块 (core/risk/)

- [service.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/risk/service.py): RiskManager 类，含 `approve_verbose()` 多层级风控检查，`_audit()` 审计日志记录

**7 层风控检查**:

| 层级 | 检查项 | 规则 |
|------|--------|------|
| 1 | 总资产验证 | total_asset > 0 |
| 2 | 交易方向验证 | direction in (buy, sell) |
| 3 | 金额验证 | amount > 0 |
| 4 | ATR 波动率 | 波动率 >= 6% 时降低仓位至 5% |
| 5 | 数量验证 | quantity > 0 |
| 6 | 黑名单检查 | 不含 ST/退市 |
| 7 | 最大订单金额 | amount <= capital * 50% |

#### 7.4 数据采集调度 (core/jobs/)

- [runner.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/jobs/runner.py): `run_domain()` 根据 domain 名称分发到对应采集实现
- [common.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/jobs/common.py): JobStats 数据模型

**支持的数据域**: stock_daily, stock_financial, stock_financial_qmt, stock_news, macro_indicator, rate_daily, calendar, report_consensus, catalyst, sentiment_monitor, stock_sw_industry_simple

---

### 8. 基础设施模块

#### 8.1 统一日志服务 (infra/storage/logging_service.py)

**文件位置**: [backend/infra/storage/logging_service.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/infra/storage/logging_service.py)

基于 Python logging + RotatingFileHandler 的统一日志系统：

| 组件 | 说明 |
|------|------|
| `LoggerManager` | 单例管理器，管理所有模块的 logger 实例 |
| `UnifiedFormatter` | 统一格式: `[时间] [模块] [级别] 消息 key=value` |
| `get_logger(name)` | 获取指定模块的 logger(自动创建文件处理器) |
| `init_logging()` | 应用启动时初始化 |
| `shutdown_logging()` | 应用关闭时清理 |

**特性**: 敏感信息脱敏(API Key/手机号/身份证)、文件轮转(10MB/5个备份)、模块级隔离

#### 8.2 报告任务存储 (infra/storage/report_store.py)

**文件位置**: [backend/infra/storage/report_store.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/infra/storage/report_store.py)

| 函数 | 功能 |
|------|------|
| `create_task()` | 创建报告任务(含唯一 task_id) |
| `update_task()` | 更新任务字段 |
| `get_task()` | 获取任务记录 |
| `delete_task()` | 删除任务 |
| `list_tasks()` | 列出所有任务 |

**持久化**: JSON 文件存储于 `.ai_quant/report_tasks/`，可选 MySQL 备份
**引导加载**: 启动时从文件系统和日志中恢复历史任务

#### 8.3 RAG 检索 (infra/reports/rag.py)

**文件位置**: [backend/infra/reports/rag.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/infra/reports/rag.py)

基于 FAISS + SQLite 的 RAG 向量检索：

| 函数 | 功能 |
|------|------|
| `ingest_pdfs()` | 解析 PDF 文件，分块后写入 SQLite |
| `build_faiss_index()` | 使用 DashScope Embedding 构建 FAISS 向量索引 |
| `rag_query()` | 语义检索(含 stock_code 过滤) |
| `rag_status()` | 索引状态(文档数/块数/索引就绪) |

**存储结构**: SQLite (`documents` 表 + `chunks` 表), FAISS 索引 (`vector_store/index.faiss`)

#### 8.4 Agent 运行记录 (infra/storage/job_store.py)

**文件位置**: [backend/infra/storage/job_store.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/infra/storage/job_store.py)

内存中的 Agent 运行记录存储，最多保留 50 条，线程安全。

#### 8.5 QMT 网关客户端 (infra/qmt_gateway_client.py)

**文件位置**: [backend/infra/qmt_gateway_client.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/infra/qmt_gateway_client.py)

基于 urllib 的 QMT 网关 HTTP 客户端：

| 环境变量 | 说明 |
|---------|------|
| `AI_QUANT_QMT_GATEWAY_BASE` | 网关基础 URL |
| `AI_QUANT_QMT_GATEWAY_TOKEN` | 网关认证 Token |
| `AI_QUANT_QMT_GATEWAY_TIMEOUT` | 超时时间(默认 5s) |

---

### 9. 公共模块 (common/)

| 文件 | 组件 | 说明 |
|------|------|------|
| [response.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/common/response.py) | `ok()` / `fail()` | 统一 API 响应格式: `{success, code, message, data}` |
| [pagination.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/common/pagination.py) | `normalize_page()` | 分页参数标准化(默认 page=1, pageSize=50, max=200) |
| [errors.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/common/errors.py) | `ApiError` | 异常数据类(code/message/http_status/details) |

---

### 10. LLM 技能模块 (llm/skills/)

每个技能目录包含 `SKILL.md` 描述文件和 `scripts/` 下的可执行 Python 脚本：

| 技能名称 | 脚本 | 功能 |
|---------|------|------|
| write-report | `report_generator.py`, `five_step_analysis.py`, `prompts.py` | 研报撰写(五步法) |
| web-search-qwen | `search_market.py` | 联网搜索市场信息 |
| web-search-universal | `search.py` | 通用网页搜索 |
| read-pdf | `build_index.py`, `query_report.py`, `parse_pdf_basic.py`, `parse_pdf_ocr.py`, `fetch_financial_data.py` | PDF 解析与 RAG 查询 |
| stock-price | `get_kline.py` | 股票K线数据获取 |
| financial-analysis | `ratio_analysis.py`, `peer_compare.py` | 财务比率与同行对比分析 |
| compare-reports | `cross_period.py`, `cross_company.py` | 跨期/跨公司报告对比 |
| sentiment-analysis | `sentiment_scorer.py`, `news_fetcher.py`, `event_detector.py`, `polymarket_monitor.py` | 舆情情绪评分与事件检测 |
| strategy-backtest | `run_backtest.py` | 策略回测 |
| strategy-recommend | `recommend.py` | 策略推荐 |
| trade-order | `place_order.py`, `query_account.py`, `miniqmt_trader.py` | 交易下单与账户查询 |
| miniqmt-kline | `get_kline.py` | MiniQMT K线获取 |
| talib | `calc_indicators.py` | TA-Lib 技术指标计算 |
| backtrader | `run_backtest.py` | Backtrader 回测框架 |
| bond-credit-review | - | 债券信用评审 |
| blog-post | - | 博客文章生成 |
| investment-research | - | 投资研究 |
| query-writing | - | SQL/查询编写 |
| schema-exploration | - | 数据库模式探索 |
| biz-skill-creator | - | 业务技能创建器 |

---

### 11. 前端模块 (web)

#### 11.1 技术栈

| 依赖 | 版本 | 用途 |
|------|------|------|
| react | ^18.3.1 | UI 框架 |
| react-router-dom | ^7.3.0 | 路由管理 |
| zustand | ^5.0.3 | 状态管理 |
| echarts | ^5.6.0 | 金融图表 |
| echarts-for-react | ^3.0.3 | React ECharts 封装 |
| tailwind-merge | ^3.0.2 | Tailwind CSS 工具 |
| lucide-react | ^0.511.0 | 图标库 |
| react-markdown | ^10.1.0 | Markdown 渲染 |
| remark-gfm | ^4.0.1 | GFM Markdown 扩展 |
| @dnd-kit | ^6/10 | 拖拽排序 |
| clsx | ^2.1.1 | 条件类名 |
| tailwindcss | ^3.4.17 | CSS 框架 |
| vite | ^6.3.5 | 构建工具 |
| vitest | ^2.1.9 | 单元测试 |
| playwright | ^1.60.0 | E2E 测试 |

#### 11.2 应用路由 (App.tsx)

**文件位置**: [web/src/App.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/App.tsx)

```
/ -> /home (重定向)
/home                       - 首页仪表盘
/info-access/               - 信息获取(父页面)
  /data-collection          - 数据采集任务
  /data-collection/detail   - 任务详情
  /sentiment                - 舆情监控
  /macro                    - 宏观数据
  /financial-hot            - 财经热点
  /data-delivery            - 数据投送
/reports                    - 研报中心
/watchlist                  - 自选股
/stock/:code                - 个股详情
/execution/                 - 执行监控(父页面)
  /tasks                    - 执行任务列表
  /positions                - 持仓查询
  /records                  - 成交记录
/risk/                      - 风险管理(父页面)
  /approve                  - 风控审批
  /rules                    - 风控规则
  /audit                    - 风控审计
/strategy/                  - 策略分析(父页面)
  /library                  - 策略库
  /instances                - 策略实例
  /backtest                 - 策略回测
/stock-select/              - 选股(父页面)
  /fundamental              - 基本面选股
  /factor                   - 因子选股
  /ml                       - ML选股
/opportunity/               - 机会挖掘(父页面)
  /unusual                  - 异常机会
  /limitup                  - 涨停机会
  /sector                   - 板块机会
/workflow/                  - 工作流(父页面)
  /team                     - 团队交易工作流
  /morning                  - 晨会工作流
  /dragon                   - 多空线工作流
```

#### 11.3 关键组件

**通用组件**:

| 组件 | 文件 | 说明 |
|------|------|------|
| AppShell | [AppShell.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/components/AppShell.tsx) | 布局框架(可折叠侧边栏+顶栏+市场状态) |
| AssistantDrawer | [AssistantDrawer.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/components/AssistantDrawer.tsx) | AI 助手侧边滑出面板 |
| ErrorBoundary | [ErrorBoundary.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/components/ErrorBoundary.tsx) | React 错误边界 |
| StockPicker | [StockPicker.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/components/StockPicker.tsx) | 股票搜索选择器 |
| Toast | [Toast.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/components/Toast.tsx) | 提示通知组件 |

**API 层**:
- [client.ts](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/api/client.ts): `fetchJson<T>()`, `postJson<T>()`, `fetchText()` 封装
- [types.ts](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/api/types.ts): 完整类型定义(DataSource/JobDomain/StockTechnicalRow 等)

---

### 12. 数据库迁移 (migrations/)

目录下的 SQL 文件按版本编号：

| 版本 | 文件 | 主要变更 |
|------|------|---------|
| 002 | `002_expanded_schema.sql` | 扩展 Schema |
| 003 | `003_add_created_at_field.sql` | 新增 created_at 字段 |
| 004 | `004_add_pe_pb_market_cap.sql` | 新增 PE/PB/市值字段 |
| 005 | `005_add_sim_account.sql` | 模拟账户表 |
| 005 | `005_add_sw_industry.sql` | 申万行业分类 |
| 005 | `005_add_sw_industry_simple.sql` | 申万行业简易版 |
| 005 | `005_create_performance_tables.sql` | 绩效表 |
| 006 | `006_add_sim_indexes.sql` | 模拟账户索引 |
| 006 | `006_create_signal_tables.sql` | 信号表 |
| 006 | `006_risk_management.sql` | 风控管理(MySQL) |
| 006 | `006_risk_management_sqlite.sql` | 风控管理(SQLite) |
| 007 | `007_risk_management_extended.sql` | 风控扩展 |
| 007 | `007_sentiment_monitor.sql` | 舆情监控表 |
| 008 | `008_add_performance_fields.sql` | 绩效字段扩展 |
| 008 | `008_create_signal_tables.sqlite.sql` | 信号表(SQLite) |
| 009 | `009_mainforce_identification*.sql` | 主力资金识别 |
| - | `add_watchlist_groups.sql` | 自选股分组 |

---

### 13. 运行时产物 (.ai_quant/)

| 路径 | 生成者 | 内容 | 生命周期 |
|------|--------|------|----------|
| `.ai_quant/logs/*.log` | 日志系统 | 各模块日志文件 | 轮转(10MB x 5) |
| `.ai_quant/report_outputs/*.md` | 研报 worker | 生成的 Markdown 研报 | 长期保存 |
| `.ai_quant/report_tasks/*.json` | 报告任务存储 | 任务记录 JSON | 长期保存 |
| `.ai_quant/job_runs/*.json` | Jobs API | Job 运行记录 | 长期保存 |
| `.ai_quant/reports_worker.log` | 研报 worker | 研报执行日志 | 长期累积 |
| `.ai_quant/reports_rag/pdfs/` | RAG 系统 | 原始 PDF 文档 | 手动管理 |
| `.ai_quant/reports_rag/documents.db` | RAG 系统 | 文档与分块元数据(SQLite) | 重建时覆盖 |
| `.ai_quant/reports_rag/vector_store/` | RAG 系统 | FAISS 向量索引 | 重建时覆盖 |

---

## 运行方式

### 前置要求

- Python 3.10+
- Node.js 18+
- MySQL (腾讯云 huahua_trade 数据库)
- `.env` 文件位于项目根目录

### 方式一：分别启动

#### 1. 启动后端 API

```bash
cd /Users/apple/Desktop/ai_huahua/ai_quant/backend
source /Users/apple/Desktop/ai_huahua/ai_quant/venv/bin/activate
pip install -r requirements.txt
python run_server.py
```

访问地址: `http://localhost:8000` | API 文档: `http://localhost:8000/docs`

#### 2. 启动 React 前端

```bash
cd /Users/apple/Desktop/ai_huahua/ai_quant/web
npm install
npm run dev
```

访问地址: `http://localhost:5173`

### 验证方式

```bash
# 健康检查
curl http://localhost:8000/api/v1/health
```

---

## 开发指南

### 添加新的 API 路由

1. 在 `backend/api/` 创建新的路由文件，使用 `APIRouter(prefix="/api/v1/xxx")`
2. 在 `backend/app.py` 中导入并注册 `api.include_router(xxx_router)`
3. 在 `web/src/api/client.ts` 中添加对应的 API 调用函数

### 添加新的工作流节点

1. 在 `backend/workflow/nodes/` 创建节点函数，接收 `TradingState` 返回 `dict`
2. 在 `backend/workflow/trading_state.py` 中定义 TypedDict
3. 在 `backend/workflow/trading_team_graph.py` 中添加节点和边

### 添加新的 LLM 技能

1. 在 `backend/llm/skills/` 创建技能目录，编写 `SKILL.md` 描述
2. 在 `scripts/` 下创建可执行 Python 脚本
3. 在 `report_agent.py` 或 `deepagent_engine.py` 中注册工具映射

### 运行测试

```bash
cd /Users/apple/Desktop/ai_huahua/ai_quant/backend
source /Users/apple/Desktop/ai_huahua/ai_quant/venv/bin/activate
pytest
```

前端测试:
```bash
cd /Users/apple/Desktop/ai_huahua/ai_quant/web
npm run test:run     # 单元测试
npm run e2e          # E2E 测试
```

---

## 依赖关系

### 后端核心依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| fastapi | ==0.115.12 | Web 框架 |
| uvicorn | ==0.34.2 | ASGI 服务器 |
| pydantic | ==2.11.4 | 数据校验 |
| python-dotenv | ==1.1.0 | 环境变量加载 |
| langgraph | ==0.4.5 | Agent 工作流编排 |
| langchain-community | - | LLM 集成(ChatTongyi) |
| langchain-text-splitters | - | 文档分块 |
| langchain_core | - | LangChain 核心 |
| pymysql | ==1.1.0 | MySQL 驱动 |
| faiss-cpu | - | FAISS 向量索引 |
| dashscope | - | 通义千问 API |
| PyPDF2 | - | PDF 解析 |
| numpy | - | 数值计算 |
| pandas | - | 数据分析 |

### 前端核心依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| react | ^18.3.1 | UI 框架 |
| react-router-dom | ^7.3.0 | 路由 |
| zustand | ^5.0.3 | 状态管理 |
| echarts | ^5.6.0 | 图表 |
| echarts-for-react | ^3.0.3 | 图表封装 |
| react-markdown | ^10.1.0 | Markdown |
| remark-gfm | ^4.0.1 | GFM 扩展 |
| @dnd-kit | ^6/10 | 拖拽 |
| tailwind-merge | ^3.0.2 | CSS 工具 |
| lucide-react | ^0.511.0 | 图标 |
| clsx | ^2.1.1 | 条件类名 |

---

## 版本信息

| 项目 | 说明 |
|------|------|
| 当前版本 | 0.1.0 |
| 更新日期 | 2026-05-16 |
| Python 版本 | 3.10+ |
| Node.js 版本 | 18+ |

---

*文档版本: V2.1 | 修订时间: 2026-05-16 | 本文档基于实际代码分析生成*
