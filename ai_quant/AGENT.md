# AGENTS.md

## 项目概述

AI Quant 智能量化投资系统，融合多智能体协作、缠论/海龟/网格等策略回测、QMT 实盘交易和飞书机器人交互的一站式量化投资平台。

## 技术栈

- **后端**: Python 3.10+ / FastAPI / Uvicorn
- **前端**: React 18 + TypeScript + Vite + Tailwind CSS / Zustand (状态管理) / ECharts + AntV G6 (可视化) / React Router
- **数据库**: MySQL 8.0 (开发/生产统一)
- **ORM/DB 驱动**: PyMySQL + 自定义连接池
- **LLM**: DeepSeek (通过 OpenAI 兼容 API 调用) / 自研 DeepAgent 引擎
- **策略引擎**: Backtrader / Chanpy (缠论) / TA-Lib
- **测试**: Pytest (后端) + Vitest + Playwright (前端端到端)
- **CI/CD**: GitHub Actions (backend-ci.yml)
- **部署**: Docker Compose (mysql + backend + web + streamlit)
- **其他**: Streamlit (AI 对话助手) / 飞书 WebSocket 机器人 / Tushare (数据源)

## 编码规范

### 命名规则

| 类型 | 规则 | 示例 |
|------|------|------|
| 文件名 | snake_case | `backtest_engine.py`, `stock_detail.py` |
| 类名 | PascalCase | `BacktestEngine`, `Settings` |
| 函数/变量 | snake_case | `get_settings()`, `api_key` |
| 常量 | UPPER_SNAKE_CASE | `OK_CODE = 0`, `INTERNAL_ERROR_CODE = 50000` |
| 私有方法/函数 | 前缀下划线 | `_validate_input()` |
| React 组件 | PascalCase (tsx/jsx 文件) | `StockChart.tsx` |

### 必须遵守

- 所有公开函数必须有 docstring（Google 风格）
- 所有 API 返回统一信封格式: `{"success": true/false, "code": 0, "message": "ok", "data": ...}`
  - 成功: `code=0`, `success=true`
  - 业务错误码: >= 40000（如 40001 参数校验, 40100 未认证, 40400 未找到, 42900 限流, 50000 服务端错误）
- 配置通过 frozen dataclass + 环境变量加载，不得硬编码密钥
- 数据库查询使用 `backend/core/db.py` 提供的连接池和上下文管理器

### 禁止事项

- 禁止使用 `print()` 调试，使用 `logging` 模块
- 禁止 `import *`
- 禁止在循环中进行数据库查询（N+1 问题）
- 禁止硬编码密钥、密码、Token
- 禁止在 CORS 配置中使用通配符 `*`
- API 密钥/密码必须通过环境变量注入
- [specified_env: venv] 必须使用项目虚拟环境运行

## 项目结构

```
ai_quant/
├── ai_quant/                      # 主项目代码
│   ├── backend/                   # FastAPI 后端
│   │   ├── api/                   # API 路由层 (路由注册, 请求处理)
│   │   │   ├── admin/             #   管理后台 API
│   │   │   ├── agent.py           #   AI Agent 对话
│   │   │   ├── stock_detail.py    #   股票详情
│   │   │   ├── trading_qmt.py     #   QMT 交易
│   │   │   ├── watchlist.py       #   自选股
│   │   │   ├── ...                #   其他业务接口
│   │   ├── core/                  # 核心业务逻辑层
│   │   │   ├── strategy/          #   策略引擎 (回测/优化/缠论/网格/组合)
│   │   │   ├── execution/         #   执行服务
│   │   │   ├── analysis/          #   技术分析/信号
│   │   │   ├── risk/              #   风险管理
│   │   │   ├── console/           #   早报/控制台
│   │   │   ├── data/              #   指数数据
│   │   │   ├── jobs/              #   定时任务
│   │   │   │   ├── domains/       #     任务域 (stock_daily, index_daily, catalyst 等)
│   │   │   │   ├── runner.py      #     任务执行器
│   │   │   │   └── ctrl.py        #     任务调度器
│   │   │   ├── mainforce/         #   主力识别
│   │   │   └── db.py              #   数据库连接管理
│   │   ├── agents/                # AI Agent 实现 (Router/Report/QuantTeam/DeepAgent)
│   │   ├── llm/                   # LLM 集成层
│   │   │   ├── clients/           #   LLM 客户端 (deepseek_client 等)
│   │   │   ├── tools/             #   Agent 工具集
│   │   │   ├── skills/            #   Agent 技能定义 (SKILL.md)
│   │   │   ├── deepagent_engine.py#   DeepAgent 引擎
│   │   │   └── model_factory.py   #   模型工厂
│   │   ├── workflow/              # LangGraph 工作流 (多智能体交易协作)
│   │   │   ├── nodes/             #   节点 (Charles/Kris/Trader/Zoe/Human)
│   │   │   ├── trading_team_graph.py
│   │   │   └── morning_brief_graph.py
│   │   ├── infra/                 # 基础设施层
│   │   │   ├── storage/           #   存储服务 (日志/任务/研报/舆情)
│   │   │   ├── reports/           #   智能研报 RAG
│   │   │   ├── tushare_client.py  #   Tushare 数据源客户端
│   │   │   ├── qmt_gateway_client.py # QMT 网关客户端
│   │   │   └── crypto.py          #   加密工具
│   │   ├── models/                # 数据模型 (SQLAlchemy/ORM)
│   │   ├── feishu/                # 飞书机器人
│   │   ├── common/                # 公共工具 (response, errors, pagination)
│   │   ├── scripts/               # 运维脚本
│   │   ├── migrations/            # 数据库迁移 SQL
│   │   ├── config.py              # 应用配置
│   │   └── app.py                 # FastAPI 入口
│   ├── web/                       # 前端 (React + Vite)
│   │   ├── src/                   #   前端源码
│   │   ├── public/                #   静态资源
│   │   ├── e2e/                   #   Playwright 端到端测试
│   │   └── ...configs             #   vite/ts/eslint/tailwind/postcss 配置
│   ├── scripts/                   # 项目级脚本 (启动/停止等)
│   │   └── start_all.ps1          #   一键启动 (Windows)
│   └── .github/workflows/         # CI/CD
├── ai_quant_qmt_gateway/          # QMT 交易网关 (独立服务)
│   ├── app.py                     #   网关 API
│   └── miniqmt_trader.py          #   MiniQMT 交易实现
├── qmt_gateway/                   # QMT 网关副本 (Windows 部署)
├── docker/                        # Docker 构建文件
├── docker-compose.yml             # 服务编排
└── .trae/                         # Trae IDE 配置
    ├── rules/                     #   项目规则
    ├── skills/                    #   AI 技能定义
    └── documents/                 #   项目文档
```

### 服务端口

| 服务 | 端口 |
|------|------|
| MySQL | 3306 |
| QMT Gateway | 8001 |
| FastAPI 后端 | 8000 |
| React 前端 | 5173 |
| Streamlit AI | 8501 |

## 工作流程

### 分支策略

- `main` — 稳定分支，保护分支
- `develop` — 开发分支
- `feature/<name>` — 功能分支
- `fix/<name>` — 修复分支

### 提交规范

遵循 Conventional Commits: `<type>: <description>`

常用 type: `feat` / `fix` / `refactor` / `test` / `docs` / `chore`

### CI/CD

- **触发条件**: push/PR 到 `backend/**` 路径变更时触发 `backend-ci.yml`
- **检查内容**:
  1. 安装依赖 (`pip install -r backend/requirements.txt`)
  2. 运行 Pytest + 覆盖率检查
  3. 覆盖率必须 >= 80% 方可通过
- **覆盖范围**: `app`, `common`, `job_store`, `logging_service`, `health`, `console_ceo`, `risk_kris`, `execution_ethan`, `sentiment`

### 开发启动

```bash
# Windows (一键启动)
.\scripts\start_all.ps1 -Dev

# 或分别启动
# 1. MySQL (确保 3306 端口可用)
# 2. 后端
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
# 3. 前端
cd web && npm run dev
```

### 测试

```bash
# 后端单元测试
cd backend && pytest

# 前端端到端测试
cd web && npx playwright test
```

## 特殊约束

### 安全要求

- **CORS**: 禁止配置 `*` 通配符，必须显式列出允许的域名
- **密钥管理**: 所有密钥/Token 通过环境变量注入，不得出现在代码中
- **加密**: 敏感配置使用 `backend/infra/crypto.py` 加密存储

### 性能要求

- 数据库连接使用连接池（`backend/core/db.py` 中的 `MySQLConfig` + 连接池）
- 批量操作禁止逐条 INSERT，使用 `executemany` 或批量导入
- 大查询必须分页

### 数据合规

- 数据源使用 Tushare，需遵守其 API 调用频率限制
- 股票数据仅供研究参考，不构成投资建议

### 环境约束

- Windows 环境: 使用 `venv` 虚拟环境运行，Python 路径为项目根目录的 `venv/Scripts/python.exe`
- MySQL 必须本地安装或通过 Docker 运行，数据库名称固定为 `huahua_trade`
- QMT Gateway 需在 Windows 环境下运行（依赖 MiniQMT）
