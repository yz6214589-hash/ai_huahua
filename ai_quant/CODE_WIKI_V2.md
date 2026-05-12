# AI Quant 统一量化系统 - Code Wiki V2

## 项目概述

AI Quant 是一个统一的 AI 量化交易系统，整合了多个专业 AI Agent（Charles、Zoe、Ethan、Kris、CEO）协同工作，提供数据获取、技术分析、信号生成、交易执行和风险管理的完整量化交易能力。

### 核心功能模块

| 模块 | 功能描述 | 技术实现 |
|------|---------|---------|
| **智能研报** | 基于 RAG + FAISS 向量检索与 LLM 生成结构化研报 | PyPDF2 + SQLite + FAISS + DashScope |
| **晨会简报** | 每日自动聚合市场数据生成晨会摘要 | LangGraph 工作流编排 |
| **交易执行** | QMT 直连接入与云端网关代理 | MiniQMT + FastAPI |
| **风控审批** | 7层风控规则检查与审计日志 | Kris Agent |
| **技术分析** | RSI、MACD、KDJ 等技术指标计算 | Zoe Service |
| **AI 对话** | 自然语言量化交互入口 | Router Agent + Streamlit |

### 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 后端 API | FastAPI + Pydantic | 高性能异步 API 服务 |
| 前端 | React + TypeScript + Vite | 现代化 React 应用 |
| UI 框架 | TailwindCSS + Radix UI | 原子化 CSS + 无障碍组件 |
| 状态管理 | Zustand | 轻量级状态管理 |
| 图表 | ECharts | 金融数据可视化 |
| 对话界面 | Streamlit | AI 对话机器人 |
| AI 框架 | LangGraph | Agent 工作流编排 |
| 数据库 | MySQL | 主数据存储 |
| 向量检索 | FAISS | RAG 向量索引 |

---

## 项目架构

```
ai_quant/
├── backend/                          # 后端服务
│   ├── ai_quant_api/                 # 统一 API 服务
│   │   ├── ai/                       # AI Agent 模块
│   │   │   ├── agents/               # Agent 实现
│   │   │   │   ├── quant_team_agent.py    # 量化团队 Agent
│   │   │   │   └── router_agent.py        # 意图路由 Agent
│   │   │   ├── graphs/               # 工作流图定义
│   │   │   │   └── morning_brief_graph.py  # 晨会简报工作流
│   │   │   └── tools/                # 工具定义
│   │   ├── api/                      # API 路由层
│   │   │   ├── health.py             # 健康检查
│   │   │   ├── summary.py            # 数据汇总
│   │   │   ├── data_charles.py       # 数据查询
│   │   │   ├── jobs.py               # 任务调度
│   │   │   ├── reports.py            # 研报生成
│   │   │   ├── analysis_zoe.py       # 技术分析
│   │   │   ├── execution_ethan.py    # 交易执行
│   │   │   ├── risk_kris.py          # 风险管理
│   │   │   ├── console_ceo.py        # CEO 控制台
│   │   │   ├── watchlist.py          # 自选股管理
│   │   │   ├── trading_qmt.py        # QMT 交易
│   │   │   └── agent.py              # AI Agent 入口
│   │   ├── services/                 # 服务集成层
│   │   │   ├── charles/              # Charles 数据服务
│   │   │   │   └── integration.py    # 数据集成
│   │   │   ├── zoe/                  # Zoe 分析服务
│   │   │   │   ├── integration.py    # 分析集成
│   │   │   │   └── tech_signals.py   # 技术指标
│   │   │   ├── ethan/                # Ethan 执行服务
│   │   │   │   ├── integration.py    # 执行集成
│   │   │   │   ├── models.py         # 数据模型
│   │   │   │   └── store.py          # 内存存储
│   │   │   ├── kris/                 # Kris 风控服务
│   │   │   │   └── integration.py    # 风控集成
│   │   │   ├── ceo/                  # CEO 协调服务
│   │   │   │   ├── integration.py    # 协调集成
│   │   │   │   └── morning_brief.py  # 晨会简报
│   │   │   └── reports/              # 研报服务
│   │   │       └── rag.py            # RAG 检索
│   │   ├── runtime/                  # 运行时支持
│   │   │   ├── report_store.py       # 报告任务存储
│   │   │   └── job_store.py          # Agent 运行记录
│   │   ├── models/                   # 数据模型
│   │   ├── app.py                    # FastAPI 应用入口
│   │   ├── config.py                 # 配置管理
│   │   └── db.py                     # 数据库操作
│   ├── run_server.py                 # 服务启动脚本
│   └── tests/                        # 后端测试
├── web/                              # React 前端
│   ├── src/
│   │   ├── api/                      # API 客户端
│   │   │   ├── client.ts            # HTTP 请求封装
│   │   │   └── types.ts             # TypeScript 类型
│   │   ├── components/               # 通用组件
│   │   │   ├── AppShell.tsx         # 应用外壳布局
│   │   │   ├── AssistantDrawer.tsx  # AI 助手抽屉
│   │   │   ├── Badge.tsx            # 徽章组件
│   │   │   ├── Card.tsx             # 卡片组件
│   │   │   ├── Empty.tsx            # 空状态组件
│   │   │   ├── StatusBadge.tsx      # 状态徽章
│   │   │   └── Tabs.tsx             # 标签页组件
│   │   ├── pages/                    # 页面组件
│   │   │   ├── Home.tsx             # 首页
│   │   │   ├── Jobs.tsx             # 任务管理
│   │   │   ├── Reports.tsx          # 研报中心
│   │   │   ├── Sentiment.tsx        # 舆情分析
│   │   │   ├── Data.tsx             # 数据中心
│   │   │   ├── Watchlist.tsx        # 自选股
│   │   │   ├── StockDetail.tsx      # 股票详情
│   │   │   ├── Execution.tsx         # 交易执行
│   │   │   ├── Risk.tsx             # 风险管理
│   │   │   ├── Strategy.tsx         # 策略管理
│   │   │   ├── Morning.tsx           # 晨会简报
│   │   │   └── Chat.tsx             # AI 对话
│   │   ├── hooks/                    # 自定义 Hooks
│   │   ├── lib/                      # 工具函数
│   │   └── App.tsx                   # 应用入口
│   └── package.json
├── streamlit_chat/                   # Streamlit 对话机器人
│   ├── app.py                        # 主应用
│   └── lib/
│       ├── api_client.py             # API 客户端
│       └── theme.py                  # 主题配置
├── qmt_gateway/                      # QMT 网关服务
│   ├── app.py                        # FastAPI 应用
│   ├── miniqmt_trader.py             # MiniQMT 交易封装
│   └── run_server.py                 # 服务启动
└── scripts/                           # 启动脚本
    ├── start_all.ps1                 # PowerShell 一键启动
    └── start_all.cmd                 # CMD 一键启动
```

---

## 核心模块详解

### 1. 后端 API 模块 (ai_quant_api)

#### 1.1 应用入口 (app.py)

**文件位置**: `backend/ai_quant_api/app.py`

FastAPI 应用工厂，负责：
- 创建 FastAPI 应用实例
- 配置 CORS 中间件
- 配置速率限制中间件（基于 IP）
- 配置 API 密钥认证
- 注册所有 API 路由

**关键配置**:
- 速率限制：10秒内最多200次请求（可配置）
- CORS：支持多源配置（禁止通配符）
- API 密钥：用于接口认证（可选）

**注册的路由**:
- `/api/health` - 健康检查
- `/api/summary` - 数据汇总
- `/api/data/*` - 数据查询
- `/api/watchlist/*` - 监控列表
- `/api/jobs/*` - 任务管理
- `/api/reports/*` - 研报生成
- `/api/analysis/*` - 分析服务
- `/api/execution/*` - 交易执行
- `/api/risk/*` - 风险管理
- `/api/trading/*` - QMT 交易
- `/api/console/*` - CEO 控制台
- `/api/agent/*` - AI Agent

#### 1.2 配置管理 (config.py)

**文件位置**: `backend/ai_quant_api/config.py`

配置管理模块，使用不可变数据类定义配置。

```python
@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Quant Unified API"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    api_key: str = ""
```

**环境变量**:
- `AI_QUANT_CORS_ORIGINS` - CORS 允许的源，多个用逗号分隔
- `AI_QUANT_API_KEY` - API 访问密钥

#### 1.3 数据库操作 (db.py)

**文件位置**: `backend/ai_quant_api/db.py`

提供 MySQL 数据库的连接管理和基础 CRUD 操作。

**关键函数**:

| 函数名 | 功能 | 说明 |
|--------|------|------|
| `load_mysql_config()` | 加载数据库配置 | 支持多种环境变量格式 |
| `connect()` | 建立数据库连接 | 配置自动提交和字典游标 |
| `query_dict()` | 执行查询 | 返回字典列表 |
| `execute()` | 执行单条 SQL | 返回影响行数 |
| `executemany()` | 批量执行 SQL | 提高大量插入效率 |

**环境变量支持**:
- `WUCAI_SQL_*` - 微财内部格式
- `DB_*` - 通用格式
- `MYSQL_*` - MySQL 标准格式

---

### 2. API 路由层

#### 2.1 数据 API (api/data_charles.py)

**文件位置**: `backend/ai_quant_api/api/data_charles.py`

数据查询接口，对接 Charles 数据服务。

**支持的数据集**:

| 数据集名称 | 说明 | 主键字段 |
|-----------|------|---------|
| `trade_stock_daily` | 股票日线行情 | stock_code, trade_date |
| `trade_stock_financial` | 股票财务数据 | stock_code, report_date |
| `trade_stock_news` | 股票新闻 | stock_code, published_at |
| `trade_macro_indicator` | 宏观指标 | indicator_date |
| `trade_rate_daily` | 利率日线 | rate_date |
| `trade_report_consensus` | 研报共识 | stock_code, broker |
| `trade_calendar_event` | 交易日历事件 | event_date |

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/data/summary` | 获取数据源摘要 |
| GET | `/api/data/{dataset}` | 分页查询数据集 |
| POST | `/api/export` | 导出 CSV/JSON |

**查询特性**:
- SQL 注入防护
- 支持批量股票代码查询（逗号分隔）
- 支持日期范围查询
- 流式 CSV 导出（避免内存溢出）

#### 2.2 研报 API (api/reports.py)

**文件位置**: `backend/ai_quant_api/api/reports.py`

智能研报生成核心模块。

**关键流程**:

1. **任务创建**: 创建研报任务，生成唯一 task_id
2. **后台处理**: 使用后台 worker 线程异步生成研报
3. **RAG 检索**: 如果启用 RAG，执行向量检索获取背景材料
4. **LLM 生成**: 调用 DashScope API 生成 Markdown 研报
5. **状态跟踪**: 支持轮询任务状态，检测超时

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/reports/tasks` | 查询研报任务列表 |
| POST | `/api/reports/tasks` | 创建研报任务 |
| DELETE | `/api/reports/tasks/{task_id}` | 删除研报任务 |
| POST | `/api/reports/tasks/{task_id}/retry` | 重试失败任务 |
| GET | `/api/reports/tasks/{task_id}/view` | 查看研报内容 |
| GET | `/api/reports/rag/status` | RAG 索引状态 |
| POST | `/api/reports/rag/ingest` | 触发 RAG 索引构建 |
| GET | `/api/reports/rag/query` | RAG 语义检索 |

**任务状态**:
- `waiting` - 等待执行
- `running` - 执行中
- `success` - 执行成功
- `failed` - 执行失败

**支持的模型**:
- `qwen-max` - 通义千问旗舰模型
- `deepseek` - DeepSeek-V3 模型

#### 2.3 任务调度 API (api/jobs.py)

**文件位置**: `backend/ai_quant_api/api/jobs.py`

任务调度管理接口。

**支持的 Job 域**:
- `stock_daily` - 股票每日数据
- `stock_financial` - 股票财务数据
- `stock_news` - 股票新闻
- `macro_indicator` - 宏观指标
- `rate_daily` - 利率日度数据
- `calendar` - 日历数据
- `report_consensus` - 研报共识
- `catalyst` - 催化剂事件

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/jobs/runs` | 查询任务运行记录 |
| POST | `/api/jobs/runs` | 创建任务运行记录 |
| GET | `/api/jobs/schedules` | 查询调度配置 |
| PUT | `/api/jobs/schedules/{domain}` | 更新调度配置 |

**特性**:
- 支持 Cron 表达式配置
- 任务超时检测（默认 900 秒）
- 自动标记僵尸任务为失败

#### 2.4 分析 API (api/analysis_zoe.py)

**文件位置**: `backend/ai_quant_api/api/analysis_zoe.py`

技术分析和信号生成接口。

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/analysis/status` | 获取分析服务状态 |
| GET | `/api/analysis/stocks/sample` | 获取样本股票列表 |
| GET | `/api/analysis/signals` | 获取股票技术信号 |

**技术指标**:
- RSI（相对强弱指数）
- MA（移动平均线）
- MACD（指数平滑异同移动平均线）
- KDJ（随机指标）
- 布林带

#### 2.5 执行 API (api/execution_ethan.py)

**文件位置**: `backend/ai_quant_api/api/execution_ethan.py`

交易执行接口，对接 Ethan 执行服务。

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/execution/status` | 获取执行服务状态 |
| POST | `/api/execution/tasks` | 创建执行任务 |
| GET | `/api/execution/tasks` | 列出所有执行任务 |
| GET | `/api/execution/tasks/{task_id}` | 获取指定任务详情 |

**执行策略**:
- TWAP（时间加权平均价格）
- VWAP（成交量加权平均价格）
- RL（强化学习）

#### 2.6 风控 API (api/risk_kris.py)

**文件位置**: `backend/ai_quant_api/api/risk_kris.py`

风险管理接口，对接 Kris 风控服务。

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/risk/status` | 获取风控服务状态 |
| POST | `/api/risk/approve` | 订单风控审批 |
| GET | `/api/risk/audit` | 获取风控审计日志 |

**风控检查层级**:
1. 总资产验证
2. 交易方向验证
3. 金额验证
4. 波动率检查
5. 负面新闻检查
6. 硬性持仓限制
7. 最大持仓比例警告

#### 2.7 其他 API

| 文件 | 路径前缀 | 说明 |
|------|---------|------|
| `api/health.py` | `/api/health` | 健康检查 |
| `api/summary.py` | `/api/summary` | 数据汇总 |
| `api/watchlist.py` | `/api/watchlist` | 监控列表管理 |
| `api/trading_qmt.py` | `/api/trading` | QMT 交易接口 |
| `api/console_ceo.py` | `/api/console` | CEO 控制台 |
| `api/agent.py` | `/api/agent` | AI Agent 入口 |

---

### 3. 服务集成层

#### 3.1 Charles 服务 (services/charles/)

**文件位置**: `backend/ai_quant_api/services/charles/integration.py`

数据服务集成层，对接 Charles 数据模块。

**关键函数**:

| 函数名 | 返回类型 | 说明 |
|--------|---------|------|
| `get_job_store_dir()` | `str` | 获取任务存储目录 |
| `list_job_runs()` | `list[dict]` | 列出任务运行记录 |
| `write_job_run()` | `dict` | 写入任务运行记录 |
| `get_summary()` | `dict` | 获取数据源摘要 |
| `get_watchlist()` | `dict` | 获取监控列表 |
| `add_watchlist_item()` | `dict` | 添加自选股 |
| `delete_watchlist_item()` | `dict` | 删除自选股 |
| `search_stocks()` | `dict` | 搜索股票 |

#### 3.2 Zoe 服务 (services/zoe/)

**文件位置**: `backend/ai_quant_api/services/zoe/integration.py`

分析服务集成层，对接 Zoe 分析模块。

**关键函数**:

| 函数名 | 参数 | 返回类型 | 说明 |
|--------|------|---------|------|
| `get_status()` | - | `dict` | 获取分析服务状态 |
| `get_sample_codes()` | limit | `dict` | 获取样本股票代码 |
| `get_signals()` | stock_code, start, end | `dict` | 获取技术信号 |

**技术指标计算** (`services/zoe/tech_signals.py`):
- RSI 计算
- 移动平均线计算
- MACD 计算
- KDJ 计算
- 布林带计算

#### 3.3 Ethan 服务 (services/ethan/)

**文件位置**: `backend/ai_quant_api/services/ethan/integration.py`

执行服务集成层，对接 Ethan 执行模块。

**关键函数**:

| 函数名 | 参数 | 返回类型 | 说明 |
|--------|------|---------|------|
| `get_status()` | - | `dict` | 获取执行服务状态 |
| `create_execution_task()` | payload | `dict` | 创建执行任务 |
| `list_execution_tasks()` | - | `dict` | 列出所有任务 |
| `get_execution_task()` | task_id | `dict` | 获取任务详情 |

**数据模型** (`services/ethan/models.py`):
- `ExecutionTask` - 执行任务数据类
- `TaskStatus` - 任务状态枚举

**内存存储** (`services/ethan/store.py`):
- 使用内存字典存储任务
- 线程安全的任务管理

#### 3.4 Kris 服务 (services/kris/)

**文件位置**: `backend/ai_quant_api/services/kris/integration.py`

风控服务集成层，对接 Kris 风控模块。

**关键函数**:

| 函数名 | 参数 | 返回类型 | 说明 |
|--------|------|---------|------|
| `status()` | - | `dict` | 获取风控服务状态 |
| `approve()` | payload | `dict` | 执行订单风控审批 |
| `audit()` | last_n | `dict` | 获取审计日志 |

**决策类型**:
- `APPROVE` - 批准
- `WARN` - 警告（带建议参数）
- `REJECT` - 拒绝

#### 3.5 CEO 服务 (services/ceo/)

**文件位置**: `backend/ai_quant_api/services/ceo/integration.py`

协调服务集成层，对接 CEO 协调模块。

**关键函数**:

| 函数名 | 参数 | 返回类型 | 说明 |
|--------|------|---------|------|
| `get_status()` | - | `dict` | 获取系统状态 |
| `get_overview()` | - | `dict` | 获取系统总览 |
| `trigger_morning()` | payload | `dict` | 触发晨会流程 |

**晨会简报** (`services/ceo/morning_brief.py`):
- 聚合市场数据
- 生成晨会摘要
- 输出格式化报告

---

### 4. AI Agent 模块

#### 4.1 路由 Agent (ai/agents/router_agent.py)

**文件位置**: `backend/ai_quant_api/ai/agents/router_agent.py`

意图路由，根据用户输入决定调用哪个 Agent 或工作流。

**路由规则**:

```python
def route_intent(user_input: str) -> dict[str, Any]:
    """根据用户输入路由到对应的处理模块"""
    text = (user_input or "").strip().lower()
    
    # 空输入
    if not text or text == "none":
        return {"target": "none", "reason": "empty_input"}
    
    # 晨会关键词
    if "晨会" in text:
        return {"target": "graph:morning_brief", "reason": "matched_keyword"}
    
    # 默认路由到量化助手
    return {"target": "tool:quant_assistant", "reason": "default_route"}
```

**路由策略**:
- 空输入 → `none`
- 包含"晨会"关键词 → 晨会简报工作流
- 其他 → 默认量化助手

#### 4.2 量化团队 Agent (ai/agents/quant_team_agent.py)

**文件位置**: `backend/ai_quant_api/ai/agents/quant_team_agent.py`

量化团队主 Agent，协调各专业 Agent 工作。

**关键函数**:

```python
def run_quant_assistant(user_input: str) -> dict[str, Any]:
    """运行量化助手，处理通用量化任务"""
    return {
        "message": f"已接收任务：{user_input}",
        "modules": ["charles", "zoe", "ethan", "kris", "ceo"],
    }
```

**团队成员**:
- Charles - 数据服务
- Zoe - 分析服务
- Ethan - 执行服务
- Kris - 风控服务
- CEO - 协调服务

#### 4.3 晨会简报工作流 (ai/graphs/morning_brief_graph.py)

**文件位置**: `backend/ai_quant_api/ai/graphs/morning_brief_graph.py`

基于 LangGraph 的晨会简报生成工作流。

**工作流结构**:

```
START → collect → summarize → END
```

**关键函数**:

| 函数名 | 输入 | 输出 | 说明 |
|--------|------|------|------|
| `build_graph()` | 无 | `CompiledStateGraph` | 构建并编译工作流图 |
| `collect()` | state | dict | 收集晨会信息 |
| `summarize()` | state | dict | 生成晨会摘要 |

**数据收集**:
- 股票市场状态
- 行业涨跌情况
- 重点关注个股
- 宏观事件提醒

---

### 5. 运行时支持

#### 5.1 报告任务存储 (runtime/report_store.py)

**文件位置**: `backend/ai_quant_api/runtime/report_store.py`

报告任务的全生命周期管理。

**核心功能**:
- 任务创建、状态跟踪和更新
- 本地文件系统持久化存储
- 可选的 MySQL 数据库备份
- 从报告输出和日志中引导加载历史任务

**关键函数**:

| 函数名 | 说明 |
|--------|------|
| `create_task()` | 创建新的报告生成任务 |
| `update_task()` | 更新指定任务的字段 |
| `get_task()` | 获取指定任务记录 |
| `delete_task()` | 删除指定任务 |
| `list_tasks()` | 列出所有任务记录 |

**存储位置**:
- 本地：`{project_root}/.ai_quant/report_tasks/*.json`
- MySQL：`ai_quant_report_tasks` 表

**特性**:
- 并发安全的任务读写（使用线程锁）
- 自动从文件系统和日志中恢复任务状态
- 支持 RAG 增强的报告生成模式
- 原子写入确保数据一致性

#### 5.2 Agent 运行记录存储 (runtime/job_store.py)

**文件位置**: `backend/ai_quant_api/runtime/job_store.py`

Agent 执行运行的历史记录管理。

**核心功能**:
- 运行记录的添加和查询
- 内存中的运行历史存储（最多保留 50 条）
- 线程安全的并发访问控制

**关键函数**:

| 函数名 | 说明 |
|--------|------|
| `append_run()` | 添加新的运行记录到历史列表 |
| `list_runs()` | 获取所有运行记录的列表 |

---

### 6. QMT 网关服务 (qmt_gateway)

#### 6.1 应用入口 (qmt_gateway/app.py)

**文件位置**: `qmt_gateway/app.py`

基于 FastAPI 的 QMT 网关服务。

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/connect` | 建立 QMT 连接 |
| POST | `/disconnect` | 断开 QMT 连接 |
| GET | `/state` | 查询 QMT 状态 |
| GET | `/asset` | 查询账户资产 |
| GET | `/positions` | 查询持仓 |
| GET | `/orders` | 查询订单 |
| GET | `/trades` | 查询成交 |
| GET | `/events` | 查询事件 |
| POST | `/buy` | 买入下单 |
| POST | `/sell` | 卖出下单 |
| POST | `/cancel` | 撤销订单 |

#### 6.2 MiniQMT 交易封装 (qmt_gateway/miniqmt_trader.py)

**文件位置**: `qmt_gateway/miniqmt_trader.py`

封装 XtQuant Python SDK，提供交易功能。

**关键功能**:
- 连接管理
- 资产查询
- 持仓查询
- 订单管理
- 成交查询
- 风险检查

**回调机制**:
- `on_disconnected` - 连接断开
- `on_account_status` - 账户状态变化
- `on_stock_order` - 订单回报
- `on_stock_trade` - 成交回报
- `on_order_error` - 订单错误
- `on_cancel_error` - 撤单错误

---

### 7. 前端模块 (web)

#### 7.1 应用入口 (App.tsx)

**文件位置**: `web/src/App.tsx`

React Router 路由配置。

**页面路由**:

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | Home | 首页 |
| `/jobs` | Jobs | 任务管理 |
| `/reports` | Reports | 报告中心 |
| `/sentiment` | Sentiment | 情绪分析 |
| `/sentiment/runs/:runId` | SentimentRunDetail | 情绪分析运行详情 |
| `/sentiment/stocks/:code` | SentimentStockDetail | 情绪分析股票详情 |
| `/data` | Data | 数据中心 |
| `/watchlist` | Watchlist | 监控列表 |
| `/stock/:code` | StockDetail | 股票详情 |
| `/execution` | Execution | 交易执行 |
| `/risk` | Risk | 风险管理 |
| `/strategy` | Strategy | 策略管理 |
| `/morning` | Morning | 晨会简报 |
| `/chat` | Chat | AI 对话 |

#### 7.2 API 客户端 (api/client.ts)

**文件位置**: `web/src/api/client.ts`

HTTP 客户端封装。

**关键函数**:

```typescript
export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T>
export async function postJson<T>(url: string, body: unknown): Promise<T>
export async function fetchText(url: string, init?: RequestInit): Promise<string>
```

#### 7.3 类型定义 (api/types.ts)

**文件位置**: `web/src/api/types.ts`

TypeScript 类型定义。

**核心类型**:

| 类型名 | 说明 |
|--------|------|
| `DataSource` | 数据源类型枚举 |
| `JobDomain` | 任务领域枚举 |
| `JobStatus` | 任务状态枚举 |
| `JobRunResult` | 任务运行结果 |
| `JobSchedule` | 任务调度配置 |
| `DatasetName` | 数据集名称枚举 |
| `SummaryResponse` | 数据汇总响应 |
| `PagedRows<T>` | 分页数据结构 |
| `WatchlistItem` | 监控列表项 |
| `StockSnapshot` | 股票快照数据 |
| `StockTechnicalRow` | 技术指标数据 |

**技术指标字段**:
- `ma5`, `ma10`, `ma20`, `ma60` - 移动平均线
- `rsi6`, `rsi12`, `rsi24` - RSI 相对强弱指数
- `macd_dif`, `macd_dea`, `macd_bar` - MACD 指标
- `boll_upper`, `boll_mid`, `boll_lower` - 布林带
- `kdj_k`, `kdj_d`, `kdj_j` - KDJ 随机指标

#### 7.4 应用外壳 (components/AppShell.tsx)

**文件位置**: `web/src/components/AppShell.tsx`

布局组件，包含侧边栏和顶部栏。

**功能特性**:
- 可折叠侧边栏
- 顶部搜索框
- 市场开盘状态检测（A 股开盘时间判断）
- 导航菜单

**导航菜单项**:
- 首页总览
- 数据中心
- 自选股
- 任务管理
- 研报中心
- 舆情监控
- 策略分析
- 风控中心
- 执行监控
- 晨会简报
- AI 对话

#### 7.5 页面组件

| 组件 | 文件 | 说明 |
|------|------|------|
| Chat | `pages/Chat.tsx` | AI 对话页面，支持消息发送/接收、内容复制 |
| Reports | `pages/Reports.tsx` | 研报生成页面，任务创建、状态轮询、Markdown 查看 |
| Execution | `pages/Execution.tsx` | 执行监控页面，TWAP/VWAP/RL 策略任务管理 |
| Morning | `pages/Morning.tsx` | 晨会简报页面，一键生成市场摘要 |

---

### 8. Streamlit 对话机器人 (streamlit_chat)

#### 8.1 主应用 (streamlit_chat/app.py)

**文件位置**: `streamlit_chat/app.py`

Streamlit 对话界面。

**功能特性**:
- 会话历史管理
- 统一 Agent 调用
- 路由结果显示

#### 8.2 API 客户端 (streamlit_chat/lib/api_client.py)

**文件位置**: `streamlit_chat/lib/api_client.py`

与后端 API 交互的接口。

```python
def run_agent(user_input: str) -> dict:
    """调用后端 Agent 接口"""
```

#### 8.3 主题配置 (streamlit_chat/lib/theme.py)

**文件位置**: `streamlit_chat/lib/theme.py`

主题样式配置。

---

## 运行方式

### 方式一：一键启动 (推荐)

```powershell
# PowerShell
.\scripts\start_all.ps1

# CMD
.\scripts\start_all.cmd
```

### 方式二：分别启动

#### 1. 启动后端 API

```bash
cd backend
pip install -r requirements.txt
python run_server.py
```

访问地址: `http://localhost:8000`

#### 2. 启动 React 前端

```bash
cd web
npm install
npm run dev
```

访问地址: `http://localhost:5173`

#### 3. 启动 QMT 网关

```bash
cd qmt_gateway
pip install -r requirements.txt
python run_server.py
```

访问地址: `http://localhost:8001`

#### 4. 启动 Streamlit 对话机器人

```bash
cd streamlit_chat
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

访问地址: `http://localhost:8501`

---

## 依赖关系

### 前端依赖 (web/package.json)

**运行时依赖**:

| 包名 | 版本 | 用途 |
|------|------|------|
| react | ^18.3.1 | UI 框架 |
| react-dom | ^18.3.1 | React DOM |
| react-router-dom | ^7.3.0 | 路由管理 |
| zustand | ^5.0.3 | 状态管理 |
| echarts | ^5.6.0 | 图表库 |
| echarts-for-react | ^3.0.3 | React ECharts 封装 |
| tailwind-merge | ^3.0.2 | Tailwind CSS 工具 |
| lucide-react | ^0.511.0 | 图标库 |
| @dnd-kit/* | ^6/10 | 拖拽排序 |
| clsx | ^2.1.1 | 条件类名 |

**开发依赖**:

| 包名 | 用途 |
|------|------|
| vite | 构建工具 |
| typescript | 类型系统 |
| tailwindcss | CSS 框架 |
| @vitejs/plugin-react | React 插件 |
| vitest | 单元测试 |
| @playwright/test | E2E 测试 |
| eslint | 代码检查 |

### 后端依赖

主要依赖（以 `backend/requirements.txt` 为准）：

| 包名 | 版本策略 | 用途 |
|------|----------|------|
| fastapi | 固定 `==0.115.12` | 后端 Web 框架 |
| uvicorn | 固定 `==0.34.2` | ASGI 服务器 |
| pydantic | 固定 `==2.11.4` | 请求/响应模型与校验 |
| python-dotenv | 固定 `==1.1.0` | `.env` 加载 |
| langgraph | 固定 `==0.4.5` | Agent 工作流编排 |
| pymysql | 固定 `==1.1.0` | MySQL 访问 |
| langchain-community | 未固定 | 模型/工具适配（研报脚本依赖） |
| faiss-cpu | 未固定 | 向量索引（RAG） |
| dashscope | 未固定 | 通义模型/Embedding（RAG/研报） |
| PyPDF2 | 未固定 | PDF 解析（RAG） |
| langchain-text-splitters | 未固定 | 文档分块（RAG） |
| numpy | 未固定 | 向量计算（RAG/FAISS） |

---

## 环境变量

### 后端环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AI_QUANT_CORS_ORIGINS` | `http://localhost:5173` | CORS 允许的源 |
| `AI_QUANT_API_KEY` | - | API 访问密钥 |
| `AI_QUANT_RATE_LIMIT_WINDOW_SECONDS` | `10` | 速率限制时间窗口 |
| `AI_QUANT_RATE_LIMIT_MAX` | `200` | 速率限制最大请求数 |
| `AI_QUANT_REPORT_USE_LLM` | `0` | 是否启用 LLM 研报 |
| `AI_QUANT_REPORT_TIMEOUT_SECONDS` | `300` | 研报任务超时时间 |
| `AI_QUANT_REPORT_LLM_TIMEOUT_SECONDS` | `90` | LLM 调用超时时间 |
| `AI_QUANT_CHARLES_JOB_STORE_DIR` | - | Charles 任务存储目录 |
| `DASHSCOPE_API_KEY` | - | 通义模型 API 密钥 |

### 数据库配置

**支持多种命名格式**:

| 格式前缀 | 示例变量 |
|---------|---------|
| `WUCAI_SQL_*` | `WUCAI_SQL_HOST`, `WUCAI_SQL_PORT` |
| `DB_*` | `DB_HOST`, `DB_PORT` |
| `MYSQL_*` | `MYSQL_HOST`, `MYSQL_PORT` |

---

## API 接口一览

### 健康检查

```
GET /api/health
GET /api
```

### 数据接口

```
GET /api/data/summary
GET /api/data/{dataset}?page=1&pageSize=50&stock_code=xxx&trade_date=xxx,xxx
POST /api/export
```

### 分析接口

```
GET /api/analysis/status
GET /api/analysis/stocks/sample
GET /api/analysis/signals?stock_code=xxx&start=xxx&end=xxx
```

### 执行接口

```
GET /api/execution/status
POST /api/execution/tasks
GET /api/execution/tasks
GET /api/execution/tasks/{task_id}
```

### 风控接口

```
GET /api/risk/status
POST /api/risk/approve
GET /api/risk/audit?last_n=200
```

### 控制台接口

```
GET /api/console/status
GET /api/console/overview
POST /api/console/morning/trigger
```

### Agent 接口

```
GET /api/agent/status
GET /api/agent/tools
POST /api/agent/tools/{tool_name}/run
POST /api/agent/run
GET /api/agent/runs
POST /api/agent/stream
```

### 研报接口

```
GET /api/reports/tasks
POST /api/reports/tasks
DELETE /api/reports/tasks/{task_id}
POST /api/reports/tasks/{task_id}/retry
GET /api/reports/tasks/{task_id}/view
GET /api/reports/rag/status
POST /api/reports/rag/ingest
GET /api/reports/rag/query
```

### QMT 交易接口

```
POST /api/trading/connect
POST /api/trading/disconnect
GET /api/trading/state
GET /api/trading/asset
GET /api/trading/positions
GET /api/trading/orders
GET /api/trading/trades
POST /api/trading/buy
POST /api/trading/sell
POST /api/trading/cancel
```

---

## 数据流向

```
用户请求
    ↓
FastAPI Router
    ↓
┌──────────────────────────────────────┐
│         AI Agent 模块                │
│  ┌────────────┐    ┌────────────┐   │
│  │ Router     │ →  │ Quant      │   │
│  │ Agent      │    │ Team Agent │   │
│  └────────────┘    └────────────┘   │
│  ┌────────────┐                      │
│  │ Morning    │                      │
│  │ Brief Graph│                      │
│  └────────────┘                      │
└──────────────────────────────────────┘
    ↓
服务集成层
    ↓
┌──────────────────────────────────────┐
│     外部 Agent 服务                   │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌─────┐│
│  │Charles│ │Zoe  │ │Ethan │ │Kris ││
│  └──────┘ └──────┘ └──────┘ └─────┘│
│  ┌──────┐                           │
│  │ CEO  │                           │
│  └──────┘                           │
└──────────────────────────────────────┘
```

---

## 安全建议

1. **数据库凭证**: 确保 MySQL 等数据库密码通过环境变量注入，不要硬编码
2. **CORS 配置**: 生产环境需严格限制 CORS 源，禁止使用通配符
3. **API 鉴权**: 当前版本支持 API Key 认证，建议生产环境启用
4. **日志审计**: 交易相关操作需记录完整审计日志
5. **QMT 连接**: 生产环境需配置 QMT 网关超时和熔断机制

---

## 开发指南

### 添加新的 API 路由

1. 在 `api/` 目录创建新的路由文件，如 `new_feature.py`
2. 定义 `router = APIRouter(...)`
3. 在 `app.py` 中导入并注册路由
4. 添加对应的前端 API 客户端函数

### 添加新的 Agent

1. 在 `ai/agents/` 创建新的 Agent 文件
2. 实现 Agent 核心逻辑
3. 在 `router_agent.py` 中添加路由规则
4. 在前端添加对应的 UI 组件

### 添加新的服务集成

1. 在 `services/` 创建新的服务目录
2. 实现 `integration.py` 封装外部服务调用
3. 在对应的 API 路由中集成服务
4. 添加前端交互界面

### 添加新的页面

1. 在 `web/src/pages/` 创建页面组件
2. 在 `App.tsx` 中添加路由配置
3. 在 `AppShell.tsx` 中添加导航入口

---

## 故障排查

### 后端启动失败

1. 检查端口是否被占用: `lsof -i :8000`
2. 检查 Python 依赖是否完整: `pip install -r requirements.txt`
3. 检查数据库连接配置
4. 检查 `.env` 文件是否存在

### 前端启动失败

1. 检查 Node.js 版本，建议 >= 18
2. 删除 `node_modules` 重新安装: `rm -rf node_modules && npm install`
3. 检查 TypeScript 编译错误: `npm run check`

### API 调用失败

1. 检查后端服务是否运行
2. 检查 CORS 配置是否正确
3. 查看浏览器控制台网络请求详情
4. 检查 API Key 是否正确配置

### 研报生成失败

1. 检查 `DASHSCOPE_API_KEY` 是否配置
2. 检查 `AI_QUANT_REPORT_USE_LLM` 是否设置为 1
3. 查看 `.ai_quant/reports_worker.log` 日志文件
4. 检查 RAG 索引是否就绪

### QMT 连接失败

1. 检查 QMT 网关是否启动
2. 检查 QMT 终端是否运行
3. 查看连接超时设置是否合理

---

## 运行时产物

### `.ai_quant` 目录

| 路径 | 生成者 | 内容 | 生命周期 |
|------|--------|------|----------|
| `.ai_quant/reports_worker.log` | 后端研报 worker | 研报任务执行日志 | 长期累积 |
| `.ai_quant/report_outputs/*.md` | 后端研报 worker | 生成的 Markdown 研报 | 可长期保存 |
| `.ai_quant/report_tasks/*.json` | 研报任务存储 | 任务记录 JSON | 可长期保存 |
| `.ai_quant/job_runs/*.json` | Jobs API | Job 运行记录 | 可长期保存 |

### RAG 索引

| 路径 | 内容 | 说明 |
|------|------|------|
| `.ai_quant/reports_rag/pdfs/` | 原始 PDF 文档 | 财报、研报等 |
| `.ai_quant/reports_rag/documents.db` | SQLite 元数据库 | documents 和 chunks 表 |
| `.ai_quant/reports_rag/vector_store/` | FAISS 索引 | `index.faiss` 和 `index.pkl` |

---

## 版本信息

- **当前版本**: 0.1.0
- **更新日期**: 2026-05-10
- **主要框架**: FastAPI, React, LangGraph, FAISS
- **Python 版本**: 3.10+
- **Node.js 版本**: 18+

---

## 相关文档

- [PRD 需求规格说明书](./docs/PRD.md)
- [用户使用指南](./docs/USER_GUIDE.md)
- [技术交底文档](./docs/tech_handover/ai_quant_runtime_handover.md)
- [代码文档索引](./CODE_DOCS_INDEX.html)
- [架构图](../docs/diagrams/arch.drawio)

---

*文档版本：V2.0 | 修订时间：2026-05-10 | 修订人：AI Quant Team*
