# AI Quant 统一量化系统 - Code Wiki

## 项目概述

AI Quant 是一个统一的 AI 量化交易系统，整合了多个专业 AI Agent（Charles、Zoe、Ethan、Kris、CEO）协同工作，提供数据获取、技术分析、信号生成、交易执行和风险管理的完整量化交易能力。

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

---

## 项目架构

```
ai_quant/
├── backend/                          # 后端服务
│   ├── ai_quant_api/                 # 统一 API 服务
│   │   ├── ai/                       # AI Agent 模块
│   │   │   ├── agents/               # Agent 实现
│   │   │   ├── graphs/               # 工作流图定义
│   │   │   └── tools/                # 工具定义
│   │   ├── api/                      # API 路由层
│   │   ├── services/                 # 服务集成层
│   │   │   ├── charles/              # 数据服务
│   │   │   ├── zoe/                  # 分析服务
│   │   │   ├── ethan/                # 执行服务
│   │   │   ├── kris/                 # 风控服务
│   │   │   └── ceo/                  # 协调服务
│   │   ├── runtime/                  # 运行时支持
│   │   ├── models/                   # 数据模型
│   │   ├── app.py                    # FastAPI 应用入口
│   │   └── config.py                 # 配置管理
│   ├── run_server.py                 # 服务启动脚本
│   └── tests/                        # 后端测试
├── web/                              # React 前端
│   ├── src/
│   │   ├── api/                      # API 客户端
│   │   ├── components/               # 通用组件
│   │   ├── pages/                    # 页面组件
│   │   ├── hooks/                    # 自定义 Hooks
│   │   ├── lib/                      # 工具函数
│   │   └── App.tsx                   # 应用入口
│   ├── package.json
│   └── vite.config.ts
├── streamlit_chat/                   # Streamlit 对话机器人
│   ├── app.py                        # 主应用
│   └── lib/
│       ├── api_client.py             # API 客户端
│       └── theme.py                  # 主题配置
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
- 注册所有 API 路由

**关键函数**:

| 函数名 | 功能 | 返回值 |
|--------|------|--------|
| `create_app()` | 创建并配置 FastAPI 应用 | `FastAPI` |

**注册的路由**:
- `/api/health` - 健康检查
- `/api/summary` - 数据汇总
- `/api/data/*` - 数据查询
- `/api/watchlist/*` - 监控列表
- `/api/jobs/*` - 任务管理
- `/api/analysis/*` - 分析服务
- `/api/execution/*` - 交易执行
- `/api/risk/*` - 风险管理
- `/api/agent/*` - AI Agent

#### 1.2 配置管理 (config.py)

**文件位置**: `backend/ai_quant_api/config.py`

配置管理模块，使用数据类定义不可变配置。

```python
@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Quant Unified API"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
```

**环境变量**:
- `AI_QUANT_CORS_ORIGINS` - CORS 允许的源，多个用逗号分隔

#### 1.3 运行时支持 (runtime/job_store.py)

**文件位置**: `backend/ai_quant_api/runtime/job_store.py`

内存中的 Agent 运行记录存储。

**关键类和函数**:

| 名称 | 类型 | 说明 |
|------|------|------|
| `AgentRunRecord` | 数据类 | Agent 运行记录数据结构 |
| `_RUNS` | 列表 | 内存存储，最多保留 50 条 |
| `append_run()` | 函数 | 添加运行记录 |
| `list_runs()` | 函数 | 获取所有运行记录 |
| `now_iso()` | 函数 | 获取当前 ISO 格式时间 |

---

### 2. API 路由层

#### 2.1 Agent API (api/agent.py)

**文件位置**: `backend/ai_quant_api/api/agent.py`

AI Agent 统一入口。

**端点列表**:

| 方法 | 路径 | 功能 | 返回类型 |
|------|------|------|---------|
| GET | `/api/agent/status` | 获取 Agent 状态 | `dict` |
| GET | `/api/agent/tools` | 获取可用工具列表 | `dict` |
| POST | `/api/agent/tools/{tool_name}/run` | 执行指定工具 | `dict` |
| POST | `/api/agent/run` | 运行 Agent | `dict` |
| GET | `/api/agent/runs` | 获取运行历史 | `dict` |
| POST | `/api/agent/stream` | 流式运行 Agent | `StreamingResponse` |

#### 2.2 数据 API (api/data_charles.py)

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
| GET | `/api/data/{dataset}/export` | 导出 CSV |

#### 2.3 分析 API (api/analysis_zoe.py)

**文件位置**: `backend/ai_quant_api/api/analysis_zoe.py`

技术分析和信号生成接口，对接 Zoe 分析服务。

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/analysis/status` | 获取分析服务状态 |
| GET | `/api/analysis/stocks/sample` | 获取样本股票列表 |
| GET | `/api/analysis/signals` | 获取股票技术信号 |

#### 2.4 执行 API (api/execution_ethan.py)

**文件位置**: `backend/ai_quant_api/api/execution_ethan.py`

交易执行接口，对接 Ethan 执行服务。

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/execution/status` | 获取执行服务状态 |
| POST | `/api/execution/tasks` | 创建执行任务 |
| GET | `/api/execution/tasks` | 列出所有执行任务 |
| GET | `/api/execution/tasks/{task_id}` | 获取指定任务详情 |

#### 2.5 风控 API (api/risk_kris.py)

**文件位置**: `backend/ai_quant_api/api/risk_kris.py`

风险管理接口，对接 Kris 风控服务。

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/risk/status` | 获取风控服务状态 |
| POST | `/api/risk/approve` | 订单风控审批 |
| GET | `/api/risk/audit` | 获取风控审计日志 |

#### 2.6 控制台 API (api/console_ceo.py)

**文件位置**: `backend/ai_quant_api/api/console_ceo.py`

CEO 协调服务接口，统一调度各 Agent。

**端点列表**:

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/console/status` | 获取系统总览 |
| GET | `/api/console/overview` | 获取详细总览信息 |
| POST | `/api/console/morning` | 触发晨会流程 |

#### 2.7 其他 API

| 文件 | 路径前缀 | 说明 |
|------|---------|------|
| `api/health.py` | `/api/health` | 健康检查 |
| `api/summary.py` | `/api/summary` | 数据汇总 |
| `api/watchlist.py` | `/api/watchlist` | 监控列表管理 |
| `api/jobs.py` | `/api/jobs` | 任务调度管理 |

---

### 3. AI Agent 模块

#### 3.1 路由 Agent (ai/agents/router_agent.py)

**文件位置**: `backend/ai_quant_api/ai/agents/router_agent.py`

意图路由，根据用户输入决定调用哪个 Agent 或工作流。

**关键函数**:

```python
def route_intent(user_input: str) -> dict[str, Any]:
    """根据用户输入路由到对应的处理模块"""
    if "晨会" in text:
        return {"target": "graph:morning_brief", "reason": "matched_keyword"}
    return {"target": "tool:quant_assistant", "reason": "default_route"}
```

**路由规则**:
- 包含"晨会"关键词 → 晨会简报工作流
- 其他 → 默认量化助手

#### 3.2 量化团队 Agent (ai/agents/quant_team_agent.py)

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

#### 3.3 晨会简报工作流 (ai/graphs/morning_brief_graph.py)

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

---

### 4. 服务集成层

#### 4.1 Charles 服务 (services/charles/)

**文件位置**: `backend/ai_quant_api/services/charles/integration.py`

数据服务集成层，对接 Charles 数据模块。

**关键函数**:

| 函数名 | 返回类型 | 说明 |
|--------|---------|------|
| `get_job_store_dir()` | `str` | 获取任务存储目录 |
| `list_job_runs()` | `list[dict]` | 列出任务运行记录 |
| `get_summary()` | `dict` | 获取数据源摘要 |
| `get_watchlist()` | `dict` | 获取监控列表 |
| `search_stocks()` | `dict` | 搜索股票 |

#### 4.2 Zoe 服务 (services/zoe/)

**文件位置**: `backend/ai_quant_api/services/zoe/integration.py`

分析服务集成层，对接 Zoe 分析模块。

**关键函数**:

| 函数名 | 参数 | 返回类型 | 说明 |
|--------|------|---------|------|
| `get_status()` | - | `dict` | 获取分析服务状态 |
| `get_sample_codes()` | limit | `dict` | 获取样本股票代码 |
| `get_signals()` | stock_code, start, end | `dict` | 获取技术信号 |

#### 4.3 Ethan 服务 (services/ethan/)

**文件位置**: `backend/ai_quant_api/services/ethan/integration.py`

执行服务集成层，对接 Ethan 执行模块。

**关键函数**:

| 函数名 | 参数 | 返回类型 | 说明 |
|--------|------|---------|------|
| `get_status()` | - | `dict` | 获取执行服务状态 |
| `create_execution_task()` | payload | `dict` | 创建执行任务 |
| `list_execution_tasks()` | - | `dict` | 列出所有任务 |
| `get_execution_task()` | task_id | `dict` | 获取任务详情 |

#### 4.4 Kris 服务 (services/kris/)

**文件位置**: `backend/ai_quant_api/services/kris/integration.py`

风控服务集成层，对接 Kris 风控模块。

**关键函数**:

| 函数名 | 参数 | 返回类型 | 说明 |
|--------|------|---------|------|
| `status()` | - | `dict` | 获取风控服务状态 |
| `approve()` | payload | `dict` | 执行订单风控审批 |
| `audit()` | last_n | `dict` | 获取审计日志 |

#### 4.5 CEO 服务 (services/ceo/)

**文件位置**: `backend/ai_quant_api/services/ceo/integration.py`

协调服务集成层，对接 CEO 协调模块。

**关键函数**:

| 函数名 | 参数 | 返回类型 | 说明 |
|--------|------|---------|------|
| `get_status()` | - | `dict` | 获取系统状态 |
| `get_overview()` | - | `dict` | 获取系统总览 |
| `trigger_morning()` | payload | `dict` | 触发晨会流程 |

---

### 5. 前端模块 (web)

#### 5.1 应用入口 (App.tsx)

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

#### 5.2 API 客户端 (api/client.ts)

**文件位置**: `web/src/api/client.ts`

HTTP 客户端封装。

**关键函数**:

```typescript
export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T>
export async function postJson<T>(url: string, body: unknown): Promise<T>
```

#### 5.3 类型定义 (api/types.ts)

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

---

### 6. Streamlit 对话机器人 (streamlit_chat)

#### 6.1 主应用 (app.py)

**文件位置**: `streamlit_chat/app.py`

Streamlit 对话界面，通过统一 Agent 处理用户量化相关问题。

**功能特性**:
- 会话历史管理
- 统一 Agent 调用
- 路由结果显示

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

#### 3. 启动 Streamlit 对话机器人

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
| `AI_QUANT_CHARLES_JOB_STORE_DIR` | - | Charles 任务存储目录 |

### Charles 数据库配置

| 变量名 | 说明 |
|--------|------|
| `MYSQL_HOST` | MySQL 主机 |
| `MYSQL_PORT` | MySQL 端口 |
| `MYSQL_USER` | MySQL 用户 |
| `MYSQL_PASSWORD` | MySQL 密码 |
| `MYSQL_DB` | 数据库名 |

### Zoe 数据库配置

| 变量名 | 说明 |
|--------|------|
| `DB_HOST` | 数据库主机 |
| `DB_PORT` | 数据库端口 |
| `DB_USER` | 数据库用户 |
| `DB_PASSWORD` | 数据库密码 |
| `DB_NAME` | 数据库名 |

---

## API 接口一览

### 健康检查

```
GET /api/health
```

### 数据接口

```
GET /api/data/summary
GET /api/data/{dataset}
GET /api/data/{dataset}/export
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
2. **CORS 配置**: 生产环境需严格限制 CORS 源
3. **API 鉴权**: 当前版本未实现认证，建议生产环境添加 JWT 或其他鉴权机制
4. **日志审计**: 交易相关操作需记录完整审计日志

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

### 添加新的页面

1. 在 `web/src/pages/` 创建页面组件
2. 在 `App.tsx` 中添加路由配置
3. 在侧边栏组件中添加导航入口

---

## 故障排查

### 后端启动失败

1. 检查端口是否被占用: `lsof -i :8000`
2. 检查 Python 依赖是否完整: `pip install -r requirements.txt`
3. 检查数据库连接配置

### 前端启动失败

1. 检查 Node.js 版本，建议 >= 18
2. 删除 `node_modules` 重新安装: `rm -rf node_modules && npm install`
3. 检查 TypeScript 编译错误: `npm run check`

### API 调用失败

1. 检查后端服务是否运行
2. 检查 CORS 配置是否正确
3. 查看浏览器控制台网络请求详情

---

## 版本信息

- 当前版本: 0.1.0
- 更新日期: 2024
- 主要框架: FastAPI, React, LangGraph

---

# 技术交底文档（聚焦 `.ai_quant` 运行时目录）

本文以项目的运行时工作目录 `.ai_quant` 为切入点，给出一份可交接给研发/运维/测试/产品的技术说明。`.ai_quant` 不属于业务源码目录，而是系统运行过程中产生的**日志、任务产物、索引与本地缓存**的统一落盘位置。

> 当前你的本机 `.ai_quant` 目录下只看到 `reports_worker.log` 是正常的：其他子目录会在对应功能第一次运行成功时才会自动创建（例如研报成功后才会出现 `report_outputs/`）。  
> 目录清单可通过代码定位：后端研报 [reports.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/reports.py#L25-L37)、RAG [rag.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/reports/rag.py#L30-L50)、Jobs 运行记录 [integration.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/charles/integration.py#L16-L58)。

## 0. `.ai_quant` 目录技术解剖

### 0.1 目录结构（现状 + 预期）

| 路径 | 生成者 | 内容 | 生命周期 | 风险点 |
|------|--------|------|----------|--------|
| `.ai_quant/reports_worker.log` | 后端研报 worker | 研报任务执行过程日志（行文本） | 长期累积 | 未做轮转/截断，可能无限增长 |
| `.ai_quant/report_outputs/<task_id>.md` | 后端研报 worker | 单个任务最终研报 Markdown | 可长期保存 | 任务量大时占用磁盘；无清理策略 |
| `.ai_quant/reports_rag/pdfs/` | RAG ingest | PDF 原始文档（财报/研报） | 长期保存 | PDF 版权与合规；目录过大 |
| `.ai_quant/reports_rag/documents.db` | RAG ingest | SQLite 元数据库（documents/chunks） | 长期保存 | WAL 文件增长；需要备份策略 |
| `.ai_quant/reports_rag/vector_store/` | RAG build index | FAISS 索引（`index.faiss/index.pkl` 等） | 可重建 | 需要与文档版本一致；损坏需重建 |
| `.ai_quant/job_runs/*.json` | Jobs API | Job 运行记录 JSON | 可长期保存 | 当前默认路径实现存在偏差（见 0.3） |

### 0.2 `reports_worker.log` 日志格式与定位方法

- 日志写入点：`_report_log(...)`，同时输出到 stdout 与文件：[_report_log](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/reports.py#L25-L37)
- 格式：`[YYYY-MM-DD HH:MM:SS] [reports] ...`
- 示例（来自你的实际文件）：[reports_worker.log](file:///Users/apple/Desktop/ai_huahua/.ai_quant/reports_worker.log)
- 快速排障建议
  - 看到 `selected_index_dir=...` 但后续没有 `run_five_step_analysis done`：通常是五步法脚本内部异常（依赖/Key/网络/索引/权限）
  - 出现 `Operation not permitted`：典型为输出目录不可写（已在后端修复为写入 `.ai_quant/report_outputs/`）

### 0.3 Jobs 运行记录目录的实现偏差（风险评估）

`get_job_store_dir()` 默认返回 `.../ai_quant/.ai_quant/job_runs`，当前实现会在项目根目录后多拼了一层 `ai_quant/`：  
[get_job_store_dir](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/charles/integration.py#L20-L25)

这会导致你期望的 `.ai_quant/job_runs` 与实际落盘路径不一致。建议在后续迭代中统一将所有运行时落盘收敛到项目根目录的 `.ai_quant/`（见 1.3 风险清单中的“路径一致性”）。

---

## 1) 技术路线综述（选型理由 / 演进规划 / 风险评估）

### 1.1 技术选型理由（围绕 `.ai_quant`）

- 统一落盘目录 `.ai_quant`
  - 理由：将“运行时产物/缓存/索引/日志”与源码隔离，便于备份、迁移与清理；也便于容器化时挂载 volume。
- RAG 与 FAISS
  - 理由：研报生成需要可追溯引用（页码/来源），本地向量索引能在低延迟下检索大规模 PDF 文档片段；`FAISS` 是成熟的本地 ANN 方案。
- SQLite（RAG 元数据库）
  - 理由：作为本地轻量元数据与 chunk 存储，适合单机与 POC，易备份与迁移；未来可演进为 MySQL/PostgreSQL/Elastic 统一存储。
- 研报异步 worker（队列 + 后台线程）
  - 理由：避免 HTTP 请求超时；将 LLM/RAG 的长耗时任务与 API 解耦。

### 1.2 演进规划（建议）

- P0：稳定性与可观测性
  - `.ai_quant/reports_worker.log` 增加轮转策略与关键耗时指标（Step 级别耗时、检索耗时、LLM tokens）
  - 研报任务从内存存储迁移到 SQLite/MySQL（重启不丢任务）
- P1：数据与索引治理
  - RAG 文档更新与索引增量更新的“可追溯版本号”（文档 hash + 索引版本）
  - 引入离线批处理/定时器（替代内存 schedules）
- P2：上线与合规
  - 统一鉴权（JWT/API Key），对外暴露的接口最小化
  - PDF 合规与脱敏策略、版权审计

### 1.3 风险评估（与现状差距）

- 路径一致性风险：Jobs 默认目录实现存在偏差（见 0.3）
- 任务可靠性风险：研报任务在内存中，后端重启会丢失（见 [report_store.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/runtime/report_store.py)）
- 成本风险：RAG 索引与 PDF 长期增长，无清理策略
- 安全风险：后端统一 API 当前无登录态/JWT（见后端梳理结论），需网关或内网部署约束

---

## 2) 前后端技术栈明细（版本策略 / 工具链 / CI/CD）

### 2.1 后端（FastAPI）

- 语言：Python 3.10+（本地 venv）
- 框架：FastAPI + Uvicorn + Pydantic
- 数据库：MySQL（PyMySQL 连接，见 [db.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/db.py)）
- AI/工作流：LangGraph（Agent 路由与晨会图）
- RAG：PyPDF2 + langchain-text-splitters + FAISS + DashScope embedding（见 [rag.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/reports/rag.py)）
- 版本锁定策略
  - 目前：`backend/requirements.txt` 部分固定、部分未固定（可复现性一般）
  - 建议：将未固定依赖补齐 `==` 并配套 hash 锁（或引入 uv/pip-tools）

### 2.2 前端（React）

- 语言：TypeScript
- 框架：React 18 + React Router 7 + Vite 6
- 状态：Zustand
- UI：Tailwind CSS；图标 `lucide-react`
- 版本锁定策略：`package-lock.json` 已锁定依赖树

### 2.3 Streamlit（对话入口）

- 用途：提供简易对话 UI，调用后端 `/api/agent/run`（见 [api_client.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/streamlit_chat/lib/api_client.py#L9-L17)）
- 依赖：`streamlit_chat/requirements.txt` 固定版本

### 2.4 CI/CD（现状与建议）

- 现状：项目内无 GitHub Actions / GitLab CI 等 CI 配置（需补齐）
- 建议最小流水线（按“可复现、可回滚”）
  - 后端：`pip install -r backend/requirements.txt` → `pytest`
  - 前端：`npm ci` → `npm run check` → `npm run build`
  - 镜像：Docker Build（backend/web/streamlit）→ Compose e2e smoke（健康检查）

---

## 3) 技术架构图（PlantUML/DrawIO 源文件）

为保证团队可编辑与可审阅，本项目采用：
- PlantUML：用于 UML 2.5 风格图（文本可审计、便于 diff）
- DrawIO：用于产品/交互视图补充（拖拽编辑）

### 3.1 分层视图（Layered View）
- PlantUML 源：`docs/diagrams/arch_layers.puml`
- DrawIO 源：`docs/diagrams/arch.drawio`（Page: layers）

### 3.2 组件视图（Component View）
- PlantUML 源：`docs/diagrams/arch_components.puml`
- DrawIO 源：`docs/diagrams/arch.drawio`（Page: components）

### 3.3 部署视图（Deployment View）
- PlantUML 源：`docs/diagrams/arch_deployment.puml`
- DrawIO 源：`docs/diagrams/arch.drawio`（Page: deployment）

### 3.4 安全视图（Security View）
- PlantUML 源：`docs/diagrams/arch_security.puml`
- DrawIO 源：`docs/diagrams/arch.drawio`（Page: security）

---

## 4) 数据库设计（逻辑/物理/容量/索引/备份容灾）

### 4.1 逻辑模型（核心实体）

当前后端主要依赖 `huahua_trade`（或同名配置库）中以 `trade_*` 为前缀的数据表，涉及：
- 股票主数据：`trade_stock_master`
- 行情与技术指标：`trade_stock_daily`、`trade_sector_daily`
- 财务：`trade_stock_financial`
- 新闻：`trade_stock_news`
- 宏观：`trade_macro_indicator`、`trade_rate_daily`、`trade_calendar_event`
- 研报一致预期：`trade_report_consensus`
- 自选股：`trade_watchlist`
- 晨会状态筛选：`trade_stock_status`

代码引用集中在：
- 数据集浏览与导出：[data_charles.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/data_charles.py#L24-L75)
- 研报选股与名称搜索：[integration.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/charles/integration.py#L119-L170)
- 晨会简报：[morning_brief.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/ceo/morning_brief.py)

### 4.2 物理模型与索引策略（建议最小集）

由于仓库中未提交 MySQL 建表脚本，下面给出“按当前查询形态”建议的最小索引策略（便于排障与容量评估）：

- `trade_stock_master`
  - 主键/唯一键：`stock_code`
  - 普通索引：`stock_name`（支持名称搜索 like，可按需要做前缀索引或引入全文索引）
- `trade_stock_daily`
  - 复合索引：`(stock_code, trade_date)`（支撑区间查询与排序）
- `trade_watchlist`
  - 索引：`stock_code`（join 主表与去重）

### 4.3 容量估算（经验法）

- `trade_stock_daily`：按 A 股约 5000 标的、日线 5 年（约 1250 交易日）
  - 行数 ≈ 6,250,000；按行宽 200B~500B，数据量约 1.2GB~3GB（不含索引）
- RAG SQLite：chunk 数取决于 PDF 总页数与 chunk_size；建议按月归档与重建索引

### 4.4 备份与容灾（建议）

- MySQL：每日全量 + binlog；同城双活/主从（至少主从）
- `.ai_quant`：按“可重建/不可重建”分级
  - 可重建：`reports_rag/vector_store`（可重建但耗时）  
  - 不可重建：`reports_rag/pdfs`、`report_outputs`（需要备份）

---

## 5) 信息架构图（用户旅程/功能地图/导航/权限矩阵）

### 5.1 用户旅程（建议抽象）

角色通常是“内部投研/交易员”，流程可简化为：
1) 选股/自选股维护  
2) 拉取行情/财务/新闻  
3) 生成信号/风控审批  
4) 生成研报/晨会简报  
5) 交易执行（QMT 网关）

图源文件：
- PlantUML：`docs/diagrams/ia_user_journey.puml`
- 权限矩阵：`docs/diagrams/ia_permission_matrix.puml`

### 5.2 导航结构（现状）

路由与侧边栏定义见：
- 路由表：[App.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/App.tsx#L1-L43)
- 导航壳：[AppShell.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/components/AppShell.tsx#L1-L159)

### 5.3 权限矩阵（现状 + 规划）

- 现状：后端无统一鉴权；前端无登录页与角色控制
- 规划：至少区分 `viewer/analyst/trader/admin` 四类角色；交易接口默认仅 `trader/admin` 可用

---

## 6) 接口文档（REST 现状 + GraphQL 规划）

### 6.1 RESTful（现状）

后端入口聚合见 [app.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/app.py)，核心路由目录为 `backend/ai_quant_api/api/`。

#### 6.1.1 研报与 RAG（重点）

**创建研报任务**

- 方法：`POST /api/reports/tasks`
- 请求体：

```json
{
  "model": "qwen-max",
  "stock_codes": ["002410.SZ"]
}
```

- 响应（200）：

```json
{
  "task": {
    "task_id": "xxxxxxxx",
    "model": "qwen-max",
    "stock_codes": ["002410.SZ"],
    "stock_names": ["广联达"],
    "status": "waiting",
    "created_at": "2026-05-08T00:02:25",
    "started_at": null,
    "finished_at": null,
    "error_message": null,
    "report_markdown": null
  }
}
```

实现位置：[reports.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/reports.py)

**查询研报任务列表**
- 方法：`GET /api/reports/tasks?limit=100&q=&created_start=&created_end=`
- 说明：前端研报页默认每 1500ms 轮询一次（见 [Reports.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/pages/Reports.tsx#L70-L77)）

**查看研报**
- 方法：`GET /api/reports/tasks/{task_id}/view`
- 说明：成功时返回 Markdown（`text/markdown`），并同时将内容落盘到 `.ai_quant/report_outputs/{task_id}.md`

**RAG 状态/入库/检索**
- `GET /api/reports/rag/status`：查看 pdf_dir/db_path/index_dir 是否就绪
- `POST /api/reports/rag/ingest`：扫描 pdf → 写入 SQLite → 构建/更新 FAISS
- `GET /api/reports/rag/query?q=...&stock=...&k=6`：向量检索返回 chunks

RAG 实现位置：[rag.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/reports/rag.py)

#### 6.1.2 股票搜索

- 方法：`GET /api/stocks?q=广联达&limit=20`
- 返回：`{ items: [{ code, name }...] }`
- 数据来源：MySQL 表 `trade_stock_master`（优先）与 `trade_stock_daily`（补齐 name/补充结果）

实现位置：[watchlist.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/watchlist.py) 与 [integration.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/charles/integration.py#L119-L187)

建议错误码体系（现状兼容 + 规划）：

| HTTP | 含义 | 典型场景 |
|------|------|----------|
| 200 | 成功 | 正常返回 |
| 400 | 参数/前置条件不满足 | 缺索引、缺必填字段 |
| 404 | 资源不存在 | task_id 不存在 |
| 500 | 服务内部异常 | DB/脚本/第三方失败 |

鉴权流程（现状）：
- 后端统一 API：未实现 JWT/API Key
- 交易网关：转发时使用 `X-API-Token`（见 [qmt_gateway_client.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/qmt_gateway_client.py#L45-L66)）

Mock 规则（建议）：
- Web 侧使用 MSW（Mock Service Worker）拦截 `/api/*`，提供 `waiting/running/success/failed` 的研报任务状态序列，方便压测轮询与 UI 状态

变更记录（摘要）：
- 控制台晨会触发接口调整为：`POST /api/console/morning/trigger`
- 研报任务查看接口：`GET /api/reports/tasks/{task_id}/view`

### 6.2 GraphQL（规划，不代表已实现）

现状系统未实现 GraphQL Server。若要按“REST + GraphQL 双协议”落地，建议：
- 新增 `/graphql`（POST）与 `/graphiql`（可选）
- GraphQL 仅承载“聚合查询场景”（例如首页 overview、研报任务列表、watchlist + stock master 联表）
- Mutations 对齐 REST：createReportTask、deleteReportTask、approveRisk 等
- Schema 源文件（交付物）：`docs/api/graphql/schema.graphql`

---

## 7) 前端交互说明（流程/状态/可访问性/性能/埋点）

### 7.1 研报页面（关键交互）

页面实现：[Reports.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/pages/Reports.tsx#L1-L481)

- 选股：输入即搜索（150ms 防抖 + 缓存 + Abort），下拉多选展示 code+name
- 创建任务：`POST /api/reports/tasks`
- 任务列表：固定 1500ms 轮询（建议后续替换为 SSE/WebSocket 或“仅 running 时轮询”）

### 7.2 组件状态图（建议）

建议将“股票下拉多选”抽象为一个独立组件，并明确状态机：
- Idle（未聚焦）
- Open（下拉展开）
- Loading（请求中）
- Error（请求失败）
- Selected（多选集合更新）

对应图源：`docs/diagrams/ui_reports_picker_state.puml`。

### 7.3 可访问性标准（建议基线）

- 下拉列表补齐 `aria-expanded/aria-controls`，并实现方向键导航与焦点回收
- 页面主内容提供 skip link
- 颜色对比度满足 WCAG AA

### 7.4 性能指标（建议基线）

- 首屏：路由按需懒加载（减少首包）
- 研报列表：轮询降频或按状态自适应
- 网络：接口层引入简单缓存与请求去重

### 7.5 埋点方案（规划）

建议埋点事件（示例）：
- `report_create_clicked`（模型/股票数）
- `report_task_status`（task_id/status/duration）
- `stock_search`（q/latency/result_count）

---

## Docker Compose 一键验证（交付物说明）

项目当前仓库内未内置 Dockerfile/Compose，本次交付会新增：
- `docker-compose.yml`
- `docker/backend.Dockerfile`、`docker/web.Dockerfile`、`docker/streamlit.Dockerfile`
- `docker/mysql/init.sql`（最小可运行 schema）

并将 `.ai_quant` 作为 volume 挂载点，保证研报日志与产物可持久化。

---

## 团队评审 Checklist（自检用）

- [ ] `.ai_quant` 目录用途、生命周期、风险点与清理策略已写清
- [ ] 后端/前端/Streamlit 技术栈与版本策略已与代码一致
- [ ] 架构图 4 视图（分层/组件/部署/安全）提供 PlantUML 源文件并统一配色
- [ ] 信息架构（用户旅程/功能地图/导航结构/权限矩阵）已提供图源
- [ ] REST 接口已覆盖：路径、请求/响应模型、错误码、鉴权说明、Mock 规则、变更记录
- [ ] GraphQL（规划）已给出 schema 范围与落地原则（不伪造“已实现”）
- [ ] 前端交互说明已覆盖：页面流程、关键组件状态、可访问性、性能、埋点
- [ ] Docker Compose 可一键拉起（backend/web/streamlit/mysql）并能访问基础页面与 `/api/health`
