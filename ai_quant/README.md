# AI Quant — 智能量化投资系统

一站式智能量化投资平台，融合多智能体协作、缠论/海龟/网格等策略回测、QMT 实盘交易和飞书机器人交互。

## 系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      React 前端 (Vite, :5173)                    │
│  仪表盘 · 自选股 · 数据采集 · 策略回测 · 选股 · 风控 · 交易 · AI对话  │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP API
┌───────────────────────────────▼─────────────────────────────────┐
│                    FastAPI 后端 (:8000)                           │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐ ┌───────────┐ │
│  │ API层 │ │核心层 │ │Agent │ │ LLM  │ │Workflow│ │ 基础设施   │ │
│  │ 27路由│ │策略·风│ │多智能│ │DeepSe│ │LangGrp│ │Tushare·密 │ │
│  │       │ │控·数据│ │体协作│ │ek集成│ │工作流  │ │钥·存储·RAG│ │
│  └──────┘ └──────┘ └──────┘ └──────┘ └────────┘ └───────────┘ │
└───┬─────────────┬───────────────┬───────────────────────────────┘
    │             │               │
    ▼             ▼               ▼
┌───────┐  ┌────────────┐  ┌──────────────┐
│ MySQL │  │ QMT Gateway│  │ Streamlit AI │
│ :3306 │  │ (:8001)    │  │ (:8501)      │
└───────┘  └────────────┘  └──────────────┘
                   │
            ┌──────┴──────┐
            │ MiniQMT 终端 │ (Windows)
            └─────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.10+, FastAPI, Uvicorn |
| 前端框架 | React 18, TypeScript, Vite, Tailwind CSS |
| 状态管理 | Zustand |
| 可视化 | ECharts, AntV G6 |
| 数据库 | MySQL 8.0（数据库名: `huahua_trade`） |
| ORM/驱动 | PyMySQL + 自定义连接池 |
| AI/LLM | DeepSeek (OpenAI 兼容 API), 自研 DeepAgent 引擎 |
| 策略引擎 | 自研 + Chanpy (缠论) + TA-Lib |
| AI 对话 | Streamlit |
| 实盘交易 | MiniQMT (Windows QMT Gateway) |
| 数据源 | Tushare, AkShare |
| 消息推送 | 飞书 WebSocket 机器人 |
| 测试 | Pytest (后端) + Vitest + Playwright (前端 E2E) |
| CI/CD | GitHub Actions |
| 部署 | Docker Compose |

## 快速开始

### 环境要求

- Python 3.10+（使用项目虚拟环境）
- Node.js 18+
- MySQL 8.0（本地安装或 Docker）
- Windows（QMT 实盘交易依赖，回测功能跨平台可用）

### 1. 克隆项目

```bash
git clone <repo-url> ai_quant
cd ai_quant
```

### 2. 环境配置

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 复制环境变量模板
cp .env.example .env
```

编辑 `.env` 文件，填入必要配置：

```env
AI_QUANT_API_BASE=http://localhost:8000
AI_QUANT_CORS_ORIGINS=http://localhost:5173
VITE_STREAMLIT_CHAT_URL=http://localhost:8501

# 飞书机器人（可选）
FEISHU_APP_ID=
FEISHU_APP_SECRET=
```

数据库连接通过以下环境变量配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MYSQL_HOST` | localhost | 数据库地址 |
| `MYSQL_PORT` | 3306 | 数据库端口 |
| `MYSQL_USER` | root | 数据库用户 |
| `MYSQL_PASSWORD` | - | 数据库密码 |
| `MYSQL_DB` | huahua_trade | 数据库名 |

### 3. 初始化数据库

确保 MySQL 已运行，创建数据库：

```sql
CREATE DATABASE IF NOT EXISTS huahua_trade DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

运行迁移脚本（在 `backend/migrations/` 目录下按编号顺序执行），或启动后端后自动初始化部分表结构。

### 4. 启动开发服务

**方式一：一键启动（Windows）**

```powershell
.\scripts\start_all.ps1 -Dev          # 开发模式（热重载）
.\scripts\start_all.ps1 -Status        # 查看服务状态
.\scripts\start_all.ps1 -Kill          # 停止所有服务
```

**方式二：分别启动**

```bash
# 1. 后端
cd backend
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

# 2. 前端
cd web
npm install
npm run dev

# 3. AI 对话（可选）
cd streamlit_chat
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

**方式三：Docker Compose**

```bash
docker-compose up -d
```

### 5. 访问系统

| 服务 | 地址 |
|------|------|
| React 前端 | http://localhost:5173 |
| 管理后台 | http://localhost:5173/ai-admin |
| FastAPI 后端 | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/docs |
| Streamlit AI 对话 | http://localhost:8501 |

## 项目结构

```
ai_quant/
├── backend/                        # FastAPI 后端
│   ├── api/                        #   API 路由层（27 个路由模块）
│   │   ├── admin/                  #     管理后台 API（10 个模块）
│   │   ├── agent.py                #     AI Agent 对话接口
│   │   ├── watchlist.py            #     自选股接口
│   │   ├── data_charles.py         #     数据查询接口
│   │   ├── stock_select.py         #     选股接口
│   │   ├── stock_detail.py         #     个股详情接口
│   │   ├── trading_qmt.py          #     QMT 交易接口
│   │   ├── risk_kris.py            #     风控接口
│   │   ├── execution_ethan.py      #     交易执行接口
│   │   ├── analysis_zoe.py         #     技术分析接口
│   │   ├── sentiment.py            #     舆情/宏观接口
│   │   ├── signals.py              #     信号中心接口
│   │   ├── sim_account.py          #     模拟账户接口
│   │   ├── workflow_team.py        #     工作流团队接口
│   │   └── ...                     #     更多业务接口
│   ├── core/                       #   核心业务逻辑层
│   │   ├── strategy/               #     策略引擎（回测/优化/缠论/网格/组合）
│   │   ├── execution/              #     交易执行服务
│   │   ├── analysis/               #     技术分析/信号
│   │   ├── risk/                   #     风险管理
│   │   ├── console/                #     早报/CEO 控制台
│   │   ├── data/                   #     指数数据
│   │   ├── jobs/                   #     定时任务调度
│   │   ├── mainforce/              #     主力资金识别
│   │   └── db.py                   #     数据库连接池
│   ├── agents/                     #   AI Agent 实现
│   ├── llm/                        #   LLM 集成（DeepSeek, 工具集, 技能库）
│   ├── workflow/                   #   LangGraph 多智能体工作流
│   ├── infra/                      #   基础设施（Tushare, QMT 客户端, 存储, 加密, RAG）
│   ├── models/                     #   数据模型
│   ├── feishu/                     #   飞书机器人
│   ├── common/                     #   公共工具（响应封装, 错误处理, 分页）
│   ├── migrations/                 #   数据库迁移 SQL
│   ├── config.py                   #   应用配置
│   └── app.py                      #   FastAPI 入口
├── web/                            # React 前端
│   ├── src/                        #   源码
│   │   ├── components/             #     公共组件
│   │   ├── layouts/                #     布局组件
│   │   ├── pages/                  #     页面组件
│   │   ├── stores/                 #     Zustand 状态管理
│   │   ├── hooks/                  #     自定义 Hooks
│   │   ├── services/               #     API 调用封装
│   │   └── utils/                  #     工具函数
│   ├── e2e/                        #   Playwright E2E 测试
│   └── public/                     #   静态资源
├── scripts/                        # 项目脚本
├── streamlit_chat/                 # AI 对话（Streamlit）
├── docker/                         # Docker 构建文件
└── docker-compose.yml              # 服务编排
```

## 核心功能

### 策略库（25 种策略，10 大类别）

| 类别 | 策略 | 说明 |
|------|------|------|
| 均线 | 双均线交叉 | 经典 MA 金叉/死叉策略 |
| MACD | 经典、量能确认、背离、利润锁定 | 多维度 MACD 策略 |
| RSI | 经典、交叉确认 | 超买超卖信号 |
| 布林带 | 经典、中轨止损 | 波动率通道策略 |
| 偏利率 | 经典 | 均值回归策略 |
| 动量 | 经典、快速 | 趋势跟踪策略 |
| 自适应 | 趋势/震荡切换 | 市场状态自动识别 |
| 海龟交易 | 简化、完整、多周期过滤、ADX过滤、ML增强 | 经典海龟体系 |
| 缠论 | 基础三类、量价增强、多周期、ML增强 | 缠中说禅理论 |
| 网格交易 | 经典、缠论中枢、中枢-趋势联动 | 震荡市网格 |

### 回测引擎

- 完整的历史回测框架，支持多策略并行
- 参数优化器（遗传算法、网格搜索等）
- Walk-Forward 前进式分析
- 绩效指标：夏普比率、最大回撤、胜率、盈亏比等
- 基准对比（沪深300等指数）

### 多智能体协作

- **Charles（数据）** — 数据采集与预处理
- **Zoe（分析）** — 技术分析与信号生成
- **Kris（风控）** — 风险评估与仓位管理
- **Ethan（执行）** — 交易执行与订单管理
- **Human（审批）** — 人工决策审批节点
- **CEO（早报）** — 盘前简报生成

基于 LangGraph 实现多智能体工作流编排。

### AI 对话

- DeepSeek 大模型驱动的智能投资助手
- 支持 Streamlit Web 界面和飞书机器人双入口
- 内置 25+ LLM 技能：回测、股价查询、TA-Lib、选股、研报生成、PDF 阅读等

### 数据采集

- **股票日线** — 全市场 K 线（含 MA/RSI/MACD/BOLL/KDJ）
- **指数日线** — 沪深300、中证500 等
- **财务数据** — PE、PB、市值、ROE 等基本面指标
- **宏观指标** — CPI、PPI、PMI、M2、LPR
- **利率/情绪** — 中美债券收益率、VIX、恐贪指数
- **财经日历** — 重要经济事件日程
- **舆情监控** — 新闻情感分析、异常事件检测

### 交易执行

- QMT 实盘交易（Windows MiniQMT）
- 模拟账户交易
- 订单管理（下单、撤单、持仓查询）
- 审批流程（风险订单需人工确认）

### 风险管控

- 仓位限制、止损止盈规则
- 主力资金识别与跟踪
- 交易审计与绩效分析
- 多维度风控报告

## API 规范

### 统一响应格式

所有 API 接口返回统一信封格式：

```json
{
  "success": true,
  "code": 0,
  "message": "ok",
  "data": {}
}
```

| 字段 | 说明 |
|------|------|
| `success` | 请求是否成功 |
| `code` | 0 = 成功；>= 40000 = 业务错误 |
| `message` | 状态描述 |
| `data` | 响应数据 |

### 错误码范围

| 范围 | 含义 |
|------|------|
| 0 | 成功 |
| 40001-40099 | 参数校验错误 |
| 40100-40199 | 未认证 |
| 40400-40499 | 资源未找到 |
| 42900-42999 | 限流 |
| 50000+ | 服务端错误 |

### 认证

所有 `/api` 路径（除 `/api/health`）需要在请求头中携带 API 密钥：

```
x-api-key: your-api-key
```

## 测试

```bash
# 后端单元测试
cd backend && pytest

# 前端单元测试
cd web && npm test

# 前端 E2E 测试
cd web && npx playwright test
```

CI 在 push/PR 到 `backend/**` 时自动运行 Pytest，覆盖率要求 >= 80%。

## 编码规范

### 命名约定

| 类型 | 规则 | 示例 |
|------|------|------|
| 文件名 | snake_case | `backtest_engine.py` |
| 类名 | PascalCase | `BacktestEngine` |
| 函数/变量 | snake_case | `get_settings()` |
| 常量 | UPPER_SNAKE_CASE | `OK_CODE = 0` |
| React 组件 | PascalCase | `StockChart.tsx` |

### 必须遵守

- 所有公开函数须有 docstring（Google 风格）
- 使用 `logging` 模块，禁止 `print()` 调试
- 禁止硬编码密钥、密码、Token
- 数据库操作使用 `backend/core/db.py` 提供的连接池
- 禁止 `import *`
- 大查询必须分页

## 部署

### Docker Compose（推荐）

```bash
docker-compose up -d
```

启动 4 个服务：MySQL、Backend、Web、Streamlit。

### 手动部署

1. 安装 Python 依赖（虚拟环境）
2. 配置 MySQL 并执行迁移脚本
3. 启动 Uvicorn 后端服务
4. 构建并部署前端静态文件（`npm run build`）
5. 配置 Nginx 反向代理（生产环境）

## 分支与提交规范

- `main` — 稳定分支
- `develop` — 开发分支
- `feature/<name>` — 功能分支
- `fix/<name>` — 修复分支

提交遵循 Conventional Commits：`<type>: <description>`

常用 type：`feat` / `fix` / `refactor` / `test` / `docs` / `chore`

## 特殊约束

### 安全

- CORS 禁止通配符 `*`，必须显式列出允许的域名
- 所有密钥通过环境变量注入
- 敏感配置使用 `infra/crypto.py` 加密存储

### 数据

- 数据源使用 Tushare，遵守 API 频率限制
- 批量操作使用 `executemany` 或批量导入，禁止逐条 INSERT

### QMT 网关

- QMT Gateway 仅支持 Windows（依赖 MiniQMT）
- 默认端口 8001，使用 Token 认证

## 免责声明

本系统仅供学习和研究使用。股票数据不构成投资建议，实盘交易风险自负。使用前请充分了解量化交易的风险。

## License

MIT
