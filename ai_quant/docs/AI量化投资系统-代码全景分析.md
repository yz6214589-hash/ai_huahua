# AI 量化投资系统 (ai_quant) 代码全景分析

## 一、项目概览

| 维度 | 内容 |
|------|------|
| **项目名称** | AI 量化交易统一系统 (Hua Hua) |
| **架构** | 前后端分离 SPA + 独立 Streamlit 对话机器人 |
| **前端** | React 18 + TypeScript + Vite 6 + Tailwind CSS 3 + Zustand 5 |
| **AI 对话界面** | Streamlit 1.44.1 |
| **后端** | Python FastAPI + LangGraph + DeepSeek API |
| **数据库** | MySQL (主) / SQLite (辅助) |
| **回测框架** | backtrader |
| **AI 引擎** | DeepAgent + 多智能体角色系统 |
| **数据源** | Tushare API + QMT 网关 |
| **页面数** | 38 个前端页面 / 26 个后端 API 路由模块 |

---

## 二、整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (React SPA)                          │
│  AppShell (侧边栏+顶部栏) -> 38 个页面 -> API Client -> 后端 │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / SSE Streaming
                           v
┌─────────────────────────────────────────────────────────────┐
│                    后端 (FastAPI)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ API 路由层    │  │  中间件      │  │  LLM/AI 层       │  │
│  │ (26个路由)    │ -> │ CORS/限流/   │ -> │ Router Agent     │  │
│  │              │  │ API Key认证  │  │ DeepAgent 引擎   │  │
│  └──────┬───────┘  └──────────────┘  │ 17个 LLM 技能    │  │
│         │                            └──────────────────┘  │
│         v                                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              业务核心层                                   ││
│  │  Charles(数据) | Zoe(分析) | Kris(风控) | Ethan(执行)   ││
│  │  ┌─────────────── LangGraph 工作流 ──────────────────┐ ││
│  │  │  交易团队工作流: Charles->Zoe->Kris->Human->Trader│ ││
│  │  │  晨会工作流: collect->run                          │ ││
│  │  │  状态字段按角色所有权划分，完全解耦                  │ ││
│  │  └────────────────────────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────┘│
│         v                                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  策略引擎                    │  基础设施                  ││
│  │  18个量化策略 (backtrader)  │  QMT Gateway 客户端        ││
│  │  回测引擎 / 参数优化        │  Tushare 数据源            ││
│  │  Walk-Forward / 缠论/网格   │  RAG 研报检索              ││
│  │  多智能体批量回测           │  任务调度 / 日志服务        ││
│  └─────────────────────────────────────────────────────────┘│
│         v                                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  数据库层 (MySQL + PyMySQL 连接池)                       ││
│  │  数据采集层 (12个定时任务领域)                           ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│            独立 Strealit 对话界面 (端口 8501)                 │
│                                                             │
│  streamlit_chat/app.py                                      │
│    -> SSE 流式调用 /api/v1/agent/stream                     │
│    -> 对话管理 (新建/切换/删除)                              │
│    -> 工具调用详情展示                                       │
│    -> 晨会简报 HTML 渲染                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、项目目录结构

### 3.1 根目录

```
ai_quant/
├── backend/                     # Python FastAPI 后端
├── web/                         # React + TypeScript 前端
├── streamlit_chat/              # Streamlit AI 对话机器人
├── docs/                        # 文档
├── scripts/                     # 启动脚本
│   ├── start_all.sh             # 一键启动所有服务
│   └── start_inline.sh          # 内联启动
├── .env.example                 # 环境变量模板
├── requirements.txt             # Python 依赖
├── package.json                 # 前端依赖 (根级)
├── run_migration.py             # 数据库迁移脚本
├── submit_tasks.py              # 任务提交脚本
├── huahua_trade_schema.sql      # 数据库 Schema
└── .github/workflows/           # CI 配置
```

### 3.2 后端结构 `backend/`

```
backend/
├── app.py                       # FastAPI 应用入口
├── config.py                    # 全局配置管理
├── migrations_sqlite.py         # SQLite 迁移
│
├── api/                         # API 路由层 (26个文件)
│   ├── health.py                # 健康检查
│   ├── summary.py               # 数据汇总
│   ├── data_status.py           # 数据状态
│   ├── data_charles.py          # Charles 数据查询
│   ├── watchlist.py             # 自选股管理
│   ├── stock_detail.py          # 个股详情
│   ├── stock_select.py          # 选股
│   ├── stock_group.py           # 股票分组
│   ├── signals.py               # 信号中心
│   ├── jobs.py                  # 任务队列
│   ├── reports.py               # 智能研报
│   ├── analysis_zoe.py          # 技术分析/策略回测
│   ├── sentiment.py             # 舆情与宏观
│   ├── execution_ethan.py       # 交易执行
│   ├── trading_qmt.py           # QMT 交易
│   ├── risk_kris.py             # 风险管理
│   ├── console_ceo.py           # CEO 控制台
│   ├── agent.py                 # AI 智能体入口
│   ├── conversation_api.py      # 对话会话
│   ├── sim_account.py           # 模拟账户
│   ├── mainforce.py             # 主力识别
│   ├── approval.py              # 审批流程
│   ├── performance.py           # 绩效报告
│   ├── intraday.py              # 个股分时
│   ├── logs.py                  # 日志查询
│   └── workflow_team.py         # 工作流团队
│
├── agents/                      # AI 智能体层
│   ├── router_agent.py          # 意图路由
│   ├── deepagent_agent.py       # DeepAgent 智能体
│   ├── quant_team_agent.py      # 量化团队智能体
│   └── report_agent.py          # 研报智能体
│
├── core/                        # 核心业务逻辑
│   ├── db.py                    # 数据库连接池
│   ├── analysis/                # 技术分析服务
│   │   ├── service.py
│   │   └── tech_signals.py      # 技术指标计算
│   ├── data/                    # 数据层
│   ├── console/                 # 控制台服务
│   │   ├── service.py
│   │   └── morning_brief.py     # 晨报生成
│   ├── execution/               # 执行服务
│   │   ├── models.py
│   │   ├── service.py
│   │   └── store.py
│   ├── risk/                    # 风控服务
│   │   └── service.py
│   ├── jobs/                    # 定时任务
│   │   ├── runner.py
│   │   ├── common.py
│   │   └── domains/             # 12个任务领域
│   │       ├── stock_daily.py
│   │       ├── stock_financial.py
│   │       ├── stock_financial_qmt.py
│   │       ├── stock_news.py
│   │       ├── stock_group.py
│   │       ├── stock_sw_industry_simple.py
│   │       ├── macro_indicator.py
│   │       ├── rate_daily.py
│   │       ├── calendar.py
│   │       ├── report_consensus.py
│   │       ├── catalyst.py
│   │       └── sentiment_monitor.py
│   └── strategy/                # 策略引擎 (10个文件)
│       ├── strategy_registry.py     # 18个策略注册
│       ├── backtest_engine.py       # 回测引擎
│       ├── backtest_storage.py      # 回测存储
│       ├── metrics_calculator.py    # 指标计算
│       ├── benchmark_loader.py      # 基准加载
│       ├── chan_engine.py           # 缠论引擎
│       ├── grid_engine.py           # 网格引擎
│       ├── multi_agent_backtest.py  # 多智能体回测
│       ├── param_optimizer.py       # 参数优化器
│       └── walk_forward_engine.py   # Walk-Forward 验证
│
├── llm/                         # 大语言模型层
│   ├── deepagent_engine.py      # DeepAgent 引擎
│   ├── clients/
│   │   └── deepseek_client.py   # DeepSeek API 客户端
│   ├── tools/                   # LLM 工具定义
│   └── skills/                  # 17个 LLM 技能
│       ├── write-report/
│       ├── read-pdf/
│       ├── sentiment-analysis/
│       ├── stock-price/
│       ├── strategy-backtest/
│       ├── strategy-recommend/
│       ├── trade-order/
│       ├── backtrader/
│       ├── talib/
│       ├── financial-analysis/
│       ├── compare-reports/
│       ├── web-search-universal/
│       ├── web-search-qwen/
│       ├── miniqmt-kline/
│       ├── investment-research/
│       ├── bond-credit-review/
│       ├── blog-post/
│       └── biz-skill-creator/
│
├── workflow/                    # LangGraph 工作流
│   ├── trading_state.py         # 交易状态定义
│   ├── trading_team_graph.py    # 交易团队工作流图
│   ├── morning_brief_graph.py   # 晨会工作流图
│   └── nodes/                   # 工作流节点
│       ├── charles_node.py      # 投研节点
│       ├── zoe_node.py          # 信号节点
│       ├── kris_node.py         # 风控节点
│       ├── trader_node.py       # 交易节点
│       └── human_node.py        # 人工审批节点
│
├── infra/                       # 基础设施
│   ├── storage/                 # 存储服务
│   │   ├── logging_service.py
│   │   ├── job_store.py
│   │   ├── report_store.py
│   │   └── sentiment_store.py
│   ├── reports/rag.py           # RAG 研报检索
│   ├── qmt_gateway_client.py    # QMT 网关客户端
│   └── tushare_client.py        # Tushare 数据客户端
│
├── common/                      # 公共工具
│   ├── response.py              # 统一响应格式
│   ├── errors.py                # 异常类
│   └── pagination.py            # 分页工具
│
├── models/                      # 数据模型
├── migrations/                  # 22个 SQL 迁移脚本
├── scripts/                     # 后端脚本
└── tests/                       # 测试
```

### 3.3 前端结构 `web/`

```
web/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── playwright.config.ts
├── public/
│   ├── favicon.svg
│   ├── hua-hua-avatar-black.svg
│   └── hua-hua-avatar-gold.svg
│
├── src/
│   ├── main.tsx                 # 应用入口
│   ├── App.tsx                  # 路由配置 (主文件)
│   ├── index.css                # 全局样式
│   │
│   ├── api/                     # API 客户端
│   │   ├── client.ts            # 通用 HTTP 客户端
│   │   ├── types.ts             # 50+ 数据类型定义
│   │   ├── approval.ts
│   │   ├── mainforce.ts
│   │   ├── performance.ts
│   │   ├── signals.ts
│   │   └── simAccount.ts
│   │
│   ├── components/              # 17个通用组件
│   │   ├── AppShell.tsx         # 应用外壳 (侧边栏+顶栏)
│   │   ├── AssistantDrawer.tsx  # AI 助手抽屉
│   │   ├── BacktestCharts.tsx   # 回测图表
│   │   ├── Card.tsx
│   │   ├── Button.tsx
│   │   ├── Badge.tsx
│   │   ├── Tabs.tsx
│   │   ├── Toast.tsx
│   │   ├── Empty.tsx
│   │   ├── ErrorBoundary.tsx
│   │   ├── FlowDesigner.tsx     # 流程设计器 (antv/g6)
│   │   ├── StatusBadge.tsx
│   │   ├── StockPicker.tsx      # 股票搜索器
│   │   ├── StockScopeSelector.tsx
│   │   └── WalkForwardPanel.tsx
│   │
│   ├── hooks/
│   │   └── useTheme.ts
│   │
│   ├── lib/
│   │   └── utils.ts
│   │
│   ├── pages/                   # 38个页面
│   │   ├── Home.tsx
│   │   ├── Dashboard.tsx
│   │   ├── InfoAccess.tsx       # 信息获取 (路由容器)
│   │   │   ├── Jobs.tsx
│   │   │   ├── JobDetail.tsx
│   │   │   ├── WatchSentiment.tsx
│   │   │   ├── MacroData.tsx
│   │   │   ├── FinancialHot.tsx
│   │   │   ├── DataDelivery.tsx
│   │   │   └── StockGroups.tsx
│   │   ├── Watchlist.tsx
│   │   ├── StockDetail.tsx
│   │   ├── Reports.tsx
│   │   ├── StrategyAnalysis.tsx # 策略分析 (路由容器)
│   │   │   ├── StrategyLibrary.tsx
│   │   │   ├── StrategyInstances.tsx
│   │   │   ├── StrategyBacktest.tsx
│   │   │   ├── BacktestHistory.tsx
│   │   │   ├── ParamOptimizer.tsx
│   │   │   └── PerformanceReport.tsx
│   │   ├── StockSelect.tsx      # 选股 (路由容器)
│   │   │   ├── StockSelectFundamental.tsx
│   │   │   ├── StockSelectFactor.tsx
│   │   │   └── StockSelectML.tsx
│   │   ├── Opportunity.tsx      # 机会捕捉 (路由容器)
│   │   │   ├── SignalCenter.tsx
│   │   │   ├── OpportunityUnusual.tsx
│   │   │   ├── OpportunityLimitUp.tsx
│   │   │   └── OpportunitySector.tsx
│   │   ├── Execution.tsx        # 交易终端 (路由容器)
│   │   │   ├── ExecutionTasks.tsx
│   │   │   ├── ExecutionPositions.tsx
│   │   │   ├── ExecutionRecords.tsx
│   │   │   └── SimAccount.tsx
│   │   ├── Risk.tsx             # 风控中心 (路由容器)
│   │   │   ├── RiskDashboard.tsx
│   │   │   ├── RiskRules.tsx
│   │   │   ├── RiskApprove.tsx
│   │   │   ├── RiskAudit.tsx
│   │   │   └── MainForceIdentification.tsx
│   │   ├── WorkFlow.tsx         # 工作流 (路由容器)
│   │   │   ├── WorkFlowTeam.tsx
│   │   │   ├── WorkFlowMorning.tsx
│   │   │   └── WorkFlowDragon.tsx
│   │   └── NotFound.tsx
│   │
│   └── types/
│       └── approval.ts
│
├── e2e/                         # 6个 Playwright E2E 测试
└── __tests__/
```

### 3.4 Streamlit 对话界面 `streamlit_chat/`

```
streamlit_chat/
├── app.py                       # Streamlit 主入口 (~260行)
├── requirements.txt             # streamlit==1.44.1, requests==2.32.3
└── lib/
    ├── api_client.py            # 后端 API 客户端 (~90行)
    └── theme.py                 # 自定义 CSS 主题 (~35行)
```

---

## 四、功能模块详细清单

### 4.1 前端 9 大导航模块

| 模块 | 路由 | 子页面数 | 功能描述 |
|------|------|---------|---------|
| **首页** | `/home` | 1 | 系统概览仪表盘，显示关键指标 |
| **自选股** | `/watchlist` | 1 | 自选股列表管理，支持分组 |
| **信息获取** | `/info-access` | 7 | 数据采集、舆情监控、宏观数据、财经热点、数据交付、股票分组 |
| **策略分析** | `/strategy` | 7 | 策略库、实例、回测、回测历史、Walk-Forward、参数优化、绩效报告 |
| **选股** | `/stock-select` | 3 | 基本面选股、因子选股、机器学习选股 |
| **机会捕捉** | `/opportunity` | 4 | 信号中心、异动机会、涨停分析、板块机会 |
| **风控中心** | `/risk` | 6 | 风控仪表盘、主力识别、风控审批、风控规则、风控审计 |
| **交易终端** | `/execution` | 4 | 执行任务、持仓管理、执行记录、模拟账户 |
| **工作流** | `/workflow` | 3 | 团队工作流、晨会、龙虎榜 |

### 4.2 后端 API 路由模块

| 路由模块 | 文件 | 前缀 | 核心接口 |
|---------|------|------|---------|
| health | `health.py` | `/api/v1` | 健康检查 |
| summary | `summary.py` | `/api/v1` | 数据汇总概览 |
| data_status | `data_status.py` | `/api/v1` | 数据采集状态 |
| data_charles | `data_charles.py` | `/api/v1` | 数据查询 (Charles 角色) |
| watchlist | `watchlist.py` | `/api/v1` | 自选股 CRUD |
| stock_detail | `stock_detail.py` | `/api/v1` | 个股详情 + 技术指标 |
| stock_select | `stock_select.py` | `/api/v1/stock-select` | 选股 + 因子评分 |
| stock_group | `stock_group.py` | `/api/v1` | 股票分组管理 |
| jobs | `jobs.py` | `/api/v1` | 任务调度器管理 |
| reports | `reports.py` | `/api/v1` | 智能研报管理 |
| analysis_zoe | `analysis_zoe.py` | `/api/v1/analysis` | 技术分析 + 策略回测 |
| sentiment | `sentiment.py` | `/api/v1` | 舆情 + 宏观数据 |
| execution_ethan | `execution_ethan.py` | `/api/v1` | 交易执行管理 |
| trading_qmt | `trading_qmt.py` | `/api/v1` | QMT 交易接口 |
| risk_kris | `risk_kris.py` | `/api/v1` | 风控审批决策 |
| console_ceo | `console_ceo.py` | `/api/v1` | CEO 控制台/晨会 |
| agent | `agent.py` | `/api/v1` | AI 智能体入口 |
| conversation_api | `conversation_api.py` | `/api/v1` | 对话会话管理 |
| signals | `signals.py` | `/api/v1` | 信号中心 |
| sim_account | `sim_account.py` | `/api/v1` | 模拟账户 |
| mainforce | `mainforce.py` | `/api/v1` | 主力资金识别 |
| approval | `approval.py` | `/api/v1` | 审批流程管理 |
| performance | `performance.py` | `/api/v1` | 绩效报告 |
| intraday | `intraday.py` | `/api/v1` | 个股分时数据 |
| workflow_team | `workflow_team.py` | `/api/v1/workflow` | 工作流运行历史 |
| logs | `logs.py` | `/api/v1` | 日志查询 |

---

## 五、AI 智能体系统 (核心亮点)

### 5.1 三层智能体架构

```
用户输入
    |
    v
+------------------------------------------+
|  第一层: Router Agent (意图路由)           |
|  [agent.py -> router_agent.py]           |
|  关键词匹配: "晨会" -> graph:morning_brief |
|              "分析/研报" -> 量化助手       |
|              其他 -> DeepAgent            |
+-----------------------+------------------+
                        |
          +-------------+-------------+
          v              v             v
+--------------------+ +-----------+ +---------------+
| 第二层:             | | 第二层:   | | 第二层:       |
| DeepAgent 引擎      | | 量化团队  | | 晨会工作流    |
| (通用 LLM 助手)     | | 关键词路由| | (LangGraph)   |
| 17个工具/技能       | | 5个角色   | | 多行业分析    |
+---------+----------+ +-----------+ +-------+-------+
          |                                     |
          v                                     v
+------------------------------------+ +-----------------+
| 第三层:                            | | 第三层:          |
| 交易团队工作流                      | | 晨会生成服务     |
| Charles -> Zoe -> Kris -> Human    | | 行业排名+HTML   |
| -> Trader (LangGraph)              | | 报告生成         |
+------------------------------------+ +-----------------+
```

### 5.2 多角色系统 (交易团队)

团队成员定义在 [workflow/nodes/](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/workflow/nodes/) 目录:

| 角色 | 文件 | 职责 | 输入 | 输出 |
|------|------|------|------|------|
| **Charles** (投研情报官) | `charles_node.py` | 联网搜索基本面、获取K线、财务分析 | stock_code, user_question | investment_view (stance/confidence/catalysts/risks) |
| **Zoe** (技术信号官) | `zoe_node.py` | 运行MACD回测、结合观点决策方向/仓位 | investment_view, stock_code | trade_signal (direction/quantity/price) |
| **Kris** (风控官) | `kris_node.py` | 黑名单检查、ATR波动率、资金/仓位限制 | trade_signal, capital | risk_verdict (approve/warn/reject) |
| **Human** (人工审批) | `human_node.py` | 展示决策链，自动/手动批准 | trade_signal, risk_verdict | approved (True/False) |
| **Trader** (交易执行官) | `trader_node.py` | dry-run模拟或QMT Gateway实盘下单 | approved, trade_signal | trade_result (order_id, dry_run) |

### 5.3 工作流状态机

```
START -> Charles -> Zoe -> Kris
                           |
                  +--------+--------+
                  v        v        v
               reject    warn    approve
               (重试)    (继续)   (继续)
                  |        |        |
                  v        v        v
                Zoe      Human    Human
               (重试)      |        |
                          |        |
                     +----+        +----+
                     v                  v
                  否决               批准
                     |                  |
                     v                  v
                   END              Trader
                                      |
                                      v
                                     END
```

工作流状态定义的字段所有权约定 [trading_state.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/workflow/trading_state.py):

| 字段 | 所属角色 | 类型 |
|------|---------|------|
| `investment_view` | Charles | `InvestmentView` (stance/confidence/summary/catalysts/risks) |
| `trade_signal` | Zoe | `TradeSignal` (stock_code/direction/quantity/price/reason) |
| `risk_verdict` | Kris | `RiskVerdict` (decision/is_approved/reason/rule_name) |
| `approved` | Human | `Optional[bool]` |
| `trade_result` | Trader | `TradeResult` (dry_run/order_id/submitted_at/note) |
| `retry_count` | 公共 | `int` |
| `messages` | 公共 | `Annotated[list, add]` (自动合并) |

### 5.4 DeepAgent 引擎

[deepagent_engine.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/llm/deepagent_engine.py) 是通用 LLM 助手:

- **LLM 模型**: 通义千问 (qwen-plus), 通过 `ChatTongyi` 调用
- **核心方法**: 国泰君安"五步法" (信息差 -> 逻辑差 -> 预期差 -> 催化剂 -> 结论+风险闭环)
- **交互协议**: JSON 格式, 支持 `tool` 和 `final` 两种 action
- **17个工具**: web_search, query_pdf, financial_analysis, stock_price, compare_reports, strategy_backtest 等
- **会话管理**: 内存级线程存储, 支持多轮对话, 最多保留 20 条消息
- **系统提示词**: 包含当前日期时间、可用工具列表、常用股票代码、五步法方法论

### 5.5 LLM 技能 (17个)

分布在 [llm/skills/](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/llm/skills/) 目录, 每个技能包含独立可执行脚本:

| 技能目录 | 功能 |
|---------|------|
| `write-report` | 撰写研报 |
| `read-pdf` | 读取 PDF 文档 |
| `sentiment-analysis` | 情感分析 |
| `stock-price` | 股票价格/K线查询 |
| `strategy-backtest` | 策略回测 |
| `strategy-recommend` | 策略推荐 |
| `trade-order` | 交易下单 |
| `backtrader` | backtrader 集成 |
| `talib` | TA-Lib 技术指标 |
| `financial-analysis` | 财务分析 |
| `compare-reports` | 报告对比 |
| `web-search-universal` | 通用搜索 |
| `web-search-qwen` | Qwen 搜索 |
| `miniqmt-kline` | MiniQMT K 线 |
| `investment-research` | 投资研究 |
| `bond-credit-review` | 债券信用审查 |
| `blog-post` | 博客撰写 |
| `biz-skill-creator` | 业务技能创建器 |

---

## 六、策略引擎系统

### 6.1 18个量化策略

注册在 [strategy_registry.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/strategy/strategy_registry.py) 中, 基于 backtrader 框架:

**基础策略 (6个)**
| 策略 | 说明 |
|------|------|
| MA 双均线策略 | 快慢线交叉 (10/30日) |
| MACD 基础策略 | MACD 金叉死叉信号 |
| RSI 超买超卖策略 | RSI(14) 超买超卖区间 |
| 布林带突破策略 | 价格突破布林带上下轨 |
| 乖离率策略 | 价格与均线偏离程度 |
| 动量策略 | N 日价格动量 |

**增强策略 (4个)**
| 策略 | 说明 |
|------|------|
| RSI 穿越确认策略 | RSI 信号加穿越确认 |
| MACD 成交量确认策略 | MACD 信号加成交量过滤 |
| MACD 利润锁定策略 | MACD 信号加止盈止损 |
| 布林带中轨止损策略 | 布林带突破加中轨止损 |

**综合策略 (2个)**
| 策略 | 说明 |
|------|------|
| 自适应策略 | 趋势/震荡模式自动切换 |
| MACD 底背离策略 | 价格新低但 MACD 抬升 |

**海龟策略 (4个)**
| 策略 | 说明 |
|------|------|
| 简单海龟策略 | 唐奇安通道突破 |
| 完整海龟策略 | 含加仓、止损规则 |
| ADX 海龟策略 | ADX 过滤趋势强度 |
| 多周期海龟策略 | 多时间周期信号确认 |
| ML 增强海龟策略 | 机器学习辅助过滤 |

**缠论策略 (4个)**
| 策略 | 说明 |
|------|------|
| 基础三买策略 | 缠论第三类买点 |
| 量价增强缠论 | 缠论加成交量确认 |
| 多周期缠论 | 多级别联立分析 |
| ML 增强缠论 | 机器学习辅助识别 |

**网格策略 (3个)**
| 策略 | 说明 |
|------|------|
| 经典网格策略 | 固定间距网格 |
| 中枢网格策略 | 基于价格中枢的网格 |
| 中枢网格+趋势联动 | 网格加趋势过滤 |

### 6.2 策略引擎组件

| 组件 | 文件 | 功能 |
|------|------|------|
| **回测引擎** | `backtest_engine.py` | 执行回测, 返回各项指标 |
| **指标计算器** | `metrics_calculator.py` | 夏普比、最大回撤、胜率、年化收益 |
| **基准加载器** | `benchmark_loader.py` | 加载基准指数数据 |
| **参数优化器** | `param_optimizer.py` | 网格搜索参数空间 |
| **Walk-Forward** | `walk_forward_engine.py` | Walk-Forward 交叉验证 |
| **多智能体回测** | `multi_agent_backtest.py` | 批量多策略回测 |
| **缠论引擎** | `chan_engine.py` | 缠论笔/段/中枢计算 |
| **网格引擎** | `grid_engine.py` | 网格交易计算 |
| **回测存储** | `backtest_storage.py` | 回测结果持久化 |

---

## 七、数据采集系统

12个定时任务, 由 [jobs/runner.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/core/jobs/runner.py) 调度, 数据来源为 Tushare API 和 QMT 网关:

| 任务文件 | 数据内容 | 来源 |
|---------|---------|------|
| `stock_daily.py` | 股票日线行情 | Tushare |
| `stock_financial.py` | 财务数据 | Tushare |
| `stock_financial_qmt.py` | 财务数据补充 | QMT |
| `stock_news.py` | 股票新闻 | Tushare |
| `stock_group.py` | 股票分组信息 | 自建 |
| `stock_sw_industry_simple.py` | 申万行业分类 | Tushare |
| `macro_indicator.py` | 宏观指标 (GDP/CPI/PMI) | Tushare |
| `rate_daily.py` | 利率数据 | Tushare |
| `calendar.py` | 日历事件 | 自建 |
| `report_consensus.py` | 研报共识数据 | Tushare |
| `catalyst.py` | 催化剂事件 | 自建 |
| `sentiment_monitor.py` | 舆情监控数据 | 自建 |

---

## 八、前端核心实现

### 8.1 路由结构

```
AppShell (统一布局: 侧边栏 + 顶栏 + 内容区)
| -> / -> /home
| -> /home -> 首页
| -> /info-access -> 信息获取 (嵌套路由)
|   | -> data-collection -> 数据采集任务
|   | -> data-collection/detail -> 任务详情
|   | -> sentiment -> 舆情监控
|   | -> macro -> 宏观数据
|   | -> financial-hot -> 财经热点
|   | -> data-delivery -> 数据交付
|   | -> stock-groups -> 股票分组
| -> /watchlist -> 自选股
| -> /stock/:code -> 个股详情
| -> /strategy -> 策略分析 (嵌套路由)
|   | -> library -> 策略库
|   | -> instances -> 策略实例
|   | -> backtest -> 策略回测
|   | -> backtest-history -> 回测历史
|   | -> walk-forward -> Walk-Forward
|   | -> param-optimizer -> 参数优化
|   | -> performance -> 绩效报告
| -> /stock-select -> 选股 (嵌套路由)
|   | -> fundamental -> 基本面选股
|   | -> factor -> 因子选股
|   | -> ml -> 机器学习选股
| -> /opportunity -> 机会捕捉 (嵌套路由)
|   | -> signals -> 信号中心
|   | -> unusual -> 异动机会
|   | -> limitup -> 涨停分析
|   | -> sector -> 板块机会
| -> /risk -> 风控中心 (嵌套路由)
|   | -> dashboard -> 风控仪表盘
|   | -> mainforce -> 主力识别
|   | -> reports -> 风控研报
|   | -> approve -> 风控审批
|   | -> rules -> 风控规则
|   | -> audit -> 风控审计
| -> /execution -> 交易终端 (嵌套路由)
|   | -> tasks -> 执行任务
|   | -> positions -> 持仓管理
|   | -> records -> 执行记录
|   | -> sim-account -> 模拟账户
| -> /workflow -> 工作流 (嵌套路由)
|   | -> team -> 团队工作流
|   | -> morning -> 晨会
|   | -> dragon -> 龙虎榜
| -> * -> 404
```

### 8.2 核心前端组件

| 组件 | 文件 | 功能 |
|------|------|------|
| **AppShell** | `components/AppShell.tsx` | 应用外壳，含可折叠侧边栏、顶部栏、市场开盘检测、AI 助手抽屉 |
| **AssistantDrawer** | `components/AssistantDrawer.tsx` | AI 助手侧边抽屉 |
| **StockPicker** | `components/StockPicker.tsx` | 全局股票搜索器 |
| **Card** | `components/Card.tsx` | 通用卡片 (Card/CardHeader/CardBody) |
| **Button** | `components/Button.tsx` | 4种变体 x 3种尺寸 |
| **FlowDesigner** | `components/FlowDesigner.tsx` | 基于 @antv/g6 的流程图设计器 |
| **BacktestCharts** | `components/BacktestCharts.tsx` | 回测结果可视化 |
| **WalkForwardPanel** | `components/WalkForwardPanel.tsx` | Walk-Forward 分析面板 |

### 8.3 API 通信层

| 文件 | 内容 |
|------|------|
| `api/client.ts` | 通用 HTTP 客户端: `fetchJson()` / `postJson()` / `fetchText()` |
| | 自动前缀 `/api/` -> `/api/v1/` |
| | 统一错误处理, API Key 认证, 缓存控制 |
| `api/types.ts` | 50+ TypeScript 接口, 覆盖全部后端数据结构 |
| `api/approval.ts` | 审批相关 API |
| `api/mainforce.ts` | 主力识别 API |
| `api/signals.ts` | 信号相关 API |
| `api/simAccount.ts` | 模拟账户 API |
| `api/performance.ts` | 绩效报告 API |

---

## 九、Streamlit AI 投资助手 (对话机器人)

### 9.1 文件结构

```
streamlit_chat/
|-- app.py                    # Streamlit 主入口 (~260行)
|-- requirements.txt          # streamlit==1.44.1, requests==2.32.3
|-- lib/
    |-- api_client.py         # 后端 API 客户端封装 (~90行)
    |-- theme.py              # 自定义 CSS 主题 (~35行)
```

### 9.2 核心逻辑 (app.py)

**页面配置**:
```python
st.set_page_config(page_title="AI 投资助手", page_icon="A", layout="wide")
apply_theme()  # 应用自定义 CSS
```

**推荐问题** (4个预设快捷入口):
1. "请生成今日晨会简报"
2. "帮我分析贵州茅台的投资价值"
3. "最近有哪些热门板块？"
4. "推荐几只低估值蓝筹股"

**状态管理** (通过 `st.session_state`):
- `conv_list`: 历史对话列表
- `current_conv_id`: 当前对话 ID
- `chat_history`: 当前对话消息列表

### 9.3 对话处理流程

```
用户在输入框输入问题
    |
    |-- 1. _ensure_conversation() -> 获取/创建对话ID
    |-- 2. 将用户消息写入 chat_history -> 渲染
    |-- 3. add_message(conv_id, "user", prompt) -> 后端持久化
    |
    |-- 4. stream_agent(prompt) -> SSE 流式调用后端
    |      |
    |      |-- event: route -> 显示路由信息
    |      |-- event: status -> 显示处理状态
    |      |-- event: tools -> 显示可用工具数量
    |      |-- event: tool_end -> 工具调用完成 (展开器展示)
    |      |-- event: message -> 流式追加 AI 回答文本
    |      |-- event: report -> 接收晨会简报 HTML
    |      |-- event: done -> 处理完成
    |
    |-- 5. 渲染工具调用详情 (_render_tool_calls)
    |-- 6. 保存回答到 chat_history + 后端持久化
    |-- 7. 如果有 report_html -> 用 st.html() 渲染晨会简报
```

### 9.4 API 客户端 (api_client.py)

| 函数 | 后端接口 | 用途 |
|------|---------|------|
| `get_status()` | `GET /api/v1/agent/status` | 检查 Agent 状态 |
| `get_tools()` | `GET /api/v1/agent/tools` | 获取可用工具列表 |
| `get_agent_runs()` | `GET /api/v1/agent/runs` | 获取运行历史 |
| `stream_agent(input)` | `POST /api/v1/agent/stream` | SSE 流式调用 (核心) |
| `list_conversations()` | `GET /api/v1/conversations` | 获取对话列表 |
| `create_conversation(title)` | `POST /api/v1/conversations` | 创建新对话 |
| `get_conversation(conv_id)` | `GET /api/v1/conversations/{id}` | 获取对话详情 |
| `delete_conversation(conv_id)` | `DELETE /api/v1/conversations/{id}` | 删除对话 |
| `add_message(conv_id, role, content)` | `POST /api/v1/conversations/{id}/messages` | 添加消息 |

### 9.5 SSE 流式解析

```python
def stream_agent(user_input) -> Iterator[dict]:
    with requests.post(url, json={"input": user_input}, stream=True) as resp:
        for line in resp.iter_lines():
            if line.startswith("event:"):
                ev_type = line[6:].strip()   # 解析事件类型
            if line.startswith("data:"):
                payload = json.loads(line[5:].strip())  # 解析 JSON 负载
                yield {**payload, "_event": ev_type}
```

### 9.6 用户交互界面

```
+---------------------------------------------------+
|  侧边栏                    |  对话主区域             |
|  +-----------------------+  |                       |
|  | + 新建对话            |  |  用户: 帮我分析贵州茅台 |
|  |-----------------------|  |                       |
|  | 历史对话1 (当前)      |  |  AI 助手: [流式输出]   |
|  | 历史对话2             |  |  贵州茅台投资分析报告  |
|  | 历史对话3             |  |  ...                  |
|  | ...                   |  |                       |
|  |                       |  |  v 工具调用详情       |
|  |                       |  |  - web_search: 完成   |
|  |                       |  |  - stock_price: 完成  |
|  |                       |  |  - financial_analysis: 完成 |
|  |                       |  |                       |
|  |  2026-05-26           |  |  [输入框...]          |
|  +-----------------------+  |                       |
+---------------------------------------------------+
```

---

## 十、关键数据流

### 10.1 交易工作流完整流程

```
用户在前端选择股票 -> 点击"运行交易工作流"
    |
    v
POST /api/v1/agent/trading-workflow
    |
    v
run_trading_workflow(stock_code, capital)
    |
    v
LangGraph 交易团队图:
    |
    |-- Charles 节点:
    |   |-- web_search(公司基本面+行业动态)
    |   |-- get_kline(获取K线数据)
    |   |-- ratio_analysis(财务比率分析)
    |   |-- 生成 InvestmentView(stance/confidence/catalysts/risks)
    |
    |-- Zoe 节点:
    |   |-- run_backtest(MACD策略回测)
    |   |-- 结合 Charles 观点综合判断
    |   |-- 生成 TradeSignal(direction/quantity/price)
    |
    |-- Kris 节点:
    |   |-- fetch_kline_atr(计算ATR波动率)
    |   |-- 检查黑名单/资金/仓位限制
    |   |-- 生成 RiskVerdict(approve/warn/reject)
    |
    |-- 如果 Kris 否决 -> Zoe重试 (最多2次)
    |
    |-- Human 节点:
    |   |-- 自动批准(目前默认为True)
    |   |-- 设置 approved=True/False
    |
    |-- Trader 节点:
        |-- 检查 dry_run 模式(默认开启)
        |-- 模拟下单 或 通过 QMT Gateway 实盘
        |-- 生成 TradeResult(order_id/note)
```

### 10.2 晨会工作流流程

```
用户在聊天输入 "生成晨会简报"
    |
    v
Router Agent 识别 "晨会" 关键词
    |
    v
build_morning_graph() -> LangGraph:
    |
    |-- collect 节点:
    |   |-- 初始化参数 (行业层级/数量/回溯天数等)
    |
    |-- run 节点:
        |-- 查询行业排名 (MySQL)
        |-- 计算各行业综合评分
        |-- 按阶段分类 (加速/钝化/下跌/抄底)
        |-- 生成 Markdown 报告
        |-- 生成 HTML 报告
        |-- 持久化到 trade_morning_brief 表
```

### 10.3 DeepAgent 智能问答流程

```
用户在聊天输入问题
    |
    v
POST /api/v1/agent/run 或 SSE /api/v1/agent/stream
    |
    v
route_intent() 路由判断:
    |
    |-- 关键词 "晨会" -> 晨会工作流
    |
    |-- 其他 -> run_deepagent(input, thread_id):
        |
        |-- 1. 构建 System Prompt
        |   |-- 当前日期时间
        |   |-- 可用工具列表
        |   |-- 常用股票代码
        |   |-- 五步法方法论
        |
        |-- 2. LLM 多轮思考 (max_steps=6)
        |
        |-- 3. 工具调用循环:
        |   |-- web_search -> 联网搜索
        |   |-- financial_analysis -> 财务分析
        |   |-- stock_price -> 股票行情
        |   |-- strategy_backtest -> 策略回测
        |   |-- ... 其他工具
        |
        |-- 4. 输出 JSON:
            {"action":"final","text":"研报/分析结果"}
```

---

## 十一、技术栈汇总

| 层级 | 技术 | 用途 |
|------|------|------|
| **AI 对话前端** | Streamlit 1.44.1 | 独立对话机器人界面 |
| **前台框架** | React 18 + TypeScript | SPA UI 组件 |
| **构建工具** | Vite 6 | 构建 |
| **路由** | React Router DOM v7 | 前端路由 |
| **样式** | Tailwind CSS 3 | CSS 框架 |
| **状态管理** | Zustand 5 | 全局状态 |
| **图表** | ECharts 5 | 数据可视化 |
| **流程图** | @antv/g6 5 | 工作流可视化 |
| **图标** | lucide-react | 图标库 |
| **后端框架** | FastAPI | Python Web 框架 |
| **工作流引擎** | LangGraph | AI 工作流编排 |
| **LLM 接入** | DeepSeek API + ChatTongyi (qwen-plus) | AI 能力 |
| **回测框架** | backtrader | 策略回测 |
| **数据库** | MySQL (PyMySQL 连接池) | 主存储 |
| **技术指标** | TA-Lib + 自实现 | 指标计算 |
| **数据源** | Tushare API + QMT 网关 | 行情/财务/新闻数据 |
| **文件存储** | `.ai_quant/` 目录 | 日志/审计/配置持久化 |

---

## 十二、代码统计

| 模块 | 文件数 | 说明 |
|------|--------|------|
| 后端 API 路由 | 26 个 | `api/*.py` |
| 后端 Core 服务 | 20+ 个 | `core/*/service.py` |
| 策略引擎 | 10 个 | `core/strategy/*.py` |
| 定时任务 | 12 个 | `core/jobs/domains/*.py` |
| LLM 技能 | 17 个 | `llm/skills/*/` |
| AI 智能体 | 4 个 | `agents/*.py` |
| 工作流节点 | 5 个 | `workflow/nodes/*.py` |
| 基础设施 | 6 个 | `infra/*/` |
| 数据库迁移 | 22 个 | `migrations/*.sql` |
| 前端页面 | 38 个 | `web/src/pages/*.tsx` |
| 前端组件 | 17 个 | `web/src/components/*.tsx` |
| 前端 API | 7 个 | `web/src/api/*.ts` |
| Streamlit 界面 | 3 个 | `streamlit_chat/` |
| E2E 测试 | 6 个 | `web/e2e/*.spec.ts` |

---

## 十三、启动方式

### 13.1 一键启动 (推荐)

```bash
./scripts/start_all.sh
```

启动 3 个服务:
- FastAPI 后端: `http://localhost:8000` (docs: `/docs`)
- React 前端: `http://localhost:5173`
- Streamlit AI 助手: `http://localhost:8501`

### 13.2 单独启动

```bash
# 后端
cd backend && uvicorn app:app --reload --port 8000

# React 前端
cd web && npm run dev

# Streamlit AI 助手
cd streamlit_chat && streamlit run app.py --server.port 8501
```

---

## 十四、环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `AI_QUANT_CORS_ORIGINS` | CORS 允许来源 | `http://localhost:5173` |
| `AI_QUANT_API_KEY` | API 密钥 (为空则不启用) | `""` |
| `AI_QUANT_LOG_LEVEL` | 日志级别 | `INFO` |
| `AI_QUANT_LOG_DIR` | 日志目录 | `.ai_quant/logs` |
| `AI_QUANT_RATE_LIMIT_WINDOW_SECONDS` | 限流时间窗口 | `10` |
| `AI_QUANT_RATE_LIMIT_MAX` | 限流最大请求数 | `200` |
| `AI_QUANT_AGENT_MODEL` | LLM 模型名 | `qwen-plus` |
| `DASHSCOPE_API_KEY` | 通义千问 API 密钥 | `""` (必填) |
| `AI_QUANT_API_BASE` | Streamlit 连接的后端地址 | `http://localhost:8000` |
| `TRADER_DRY_RUN` | 交易模拟模式 | `1` (开启) |
| `WUCAI_SQL_*` / `MYSQL_*` | 数据库连接配置 | 多种命名兼容 |
