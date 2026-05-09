# `.ai_quant` 运行时目录技术交底（深度分析）

本文档聚焦运行时目录 `/Users/apple/Desktop/ai_huahua/.ai_quant`，并以该目录为主线，补齐前后端技术栈、架构视图、数据库、信息架构、接口与前端交互等交付要素。所有路径与实现均以当前仓库代码为准，敏感信息统一以 `***` 脱敏表示。

## 0. 目录现状与定位

### 0.1 当前磁盘现状（现场快照）

当前目录仅包含：

- `/Users/apple/Desktop/ai_huahua/.ai_quant/reports_worker.log`

其余子目录会在功能首次运行时按需生成（例如研报产物、RAG 文档库与向量索引）。

### 0.2 `.ai_quant` 的职责边界

`.ai_quant` 被设计为“运行时工作目录”，用于承载：

- 后端 Worker 日志：研报生成、索引选择、调用链路关键节点
- 研报产物：按任务 ID 落盘 Markdown 产物，便于追溯与审计
- RAG 数据：PDF 原文、SQLite 元数据库、FAISS 向量索引文件
- 容器化挂载点：通过 Docker volume 持久化运行时数据，实现“源码与数据分离”

对应实现入口集中在：

- 研报 API 与 worker： [reports.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/reports.py)
- RAG 服务： [rag.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/reports/rag.py)

### 0.3 运行时目录建议结构（规范）

以当前实现为准，建议把 `.ai_quant` 视为可挂载的“可清理、可重建”的运行时目录：

```
.ai_quant/
  reports_worker.log
  report_outputs/
    <task_id>.md
  reports_rag/
    pdfs/
    documents.db
    vector_store/
      index.faiss
      index.pkl
      page_info.pkl
```

其中：

- `reports_worker.log`：后端研报 worker 的关键日志落盘（便于替代断点调试）
- `report_outputs/`：研报任务成功后的 Markdown 文件输出目录
- `reports_rag/`：RAG 的文档与索引持久化目录（支持重建与增量更新）

## 1) 技术路线综述（选型理由 / 演进规划 / 风险评估）

### 1.1 技术路线（以 `.ai_quant` 为主线）

- API 层采用 FastAPI：提供统一入口，便于前端与 Streamlit 调用，并天然支持 OpenAPI
- 运行时任务采用“内存任务记录 + 后台线程队列”：实现成本低，满足单机开发/验证；研报产物落盘到 `.ai_quant/report_outputs` 提供可追溯性
- RAG 采用“SQLite 元数据库 + FAISS 索引”：本地可运行、可重建、依赖轻；索引目录默认为 `.ai_quant/reports_rag/vector_store`

关键实现位置：

- 研报任务队列与 worker： [reports.py:_TASK_QUEUE/_worker_loop](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/reports.py#L41-L251)
- 研报产物落盘： [reports.py:_process_task 写入 report_outputs](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/reports.py#L219-L240)
- RAG 路径默认值： [rag.py:get_rag_settings](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/reports/rag.py#L30-L50)

### 1.2 选型理由（简表）

| 领域 | 选型 | 理由（与 `.ai_quant` 的关系） |
|---|---|---|
| API | FastAPI + Pydantic | OpenAPI 自描述；与前端/Streamlit 对接简单；便于容器化 |
| 任务执行 | queue + thread | 研报生成属于后台耗时任务；本地验证阶段无需引入 Celery/Redis |
| RAG 元数据 | SQLite（WAL） | 单文件可挂载备份；配合 `.ai_quant` 做“可迁移运行时数据” |
| 向量索引 | FAISS | 本地可运行，索引文件可落盘在 `.ai_quant/reports_rag/vector_store` |
| 前端 | React + Vite | 交互复杂页面（研报/任务/数据）迭代快；/api 代理简单 |
| 可观测性 | 研报日志文件落盘 | 用户不做断点时，用日志串起关键链路与错误定位 |

### 1.3 演进规划（分阶段）

阶段 A（当前）：

- `.ai_quant` 承载研报日志、研报输出与 RAG 存储
- 研报任务状态存储在内存（重启即丢失），但产物落盘可追溯

阶段 B（短期演进）：

- 把“任务状态”从内存迁移到 SQLite（仍在 `.ai_quant`），消除服务重启导致 `/view 404` 的问题
- 统一所有运行记录目录到同一 `.ai_quant` 根（包含 jobs 的 job_runs）
  - 当前 jobs 默认落盘在 `repo_root/ai_quant/.ai_quant/job_runs`，实现见 [integration.py:get_job_store_dir](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/charles/integration.py#L16-L25)

阶段 C（生产化演进）：

- 任务执行迁移到分布式队列（例如 Redis + Celery/RQ），`.ai_quant` 仅保留“本机缓存/调试数据”
- 引入鉴权（JWT/OAuth2）与审计日志；将敏感配置从 `.env` 迁移到 Secret 管理

### 1.4 风险评估（与缓解策略）

| 风险 | 现状 | 影响 | 缓解建议 |
|---|---|---|---|
| 任务状态内存化 | 重启后任务丢失 | `/view` 404 或不可追溯 | 任务元数据落 SQLite（`.ai_quant`） |
| `.ai_quant` 路径不一致 | jobs 与 reports 使用不同根 | 运维与备份复杂 | 用统一 env 强制归一（Compose 已给出） |
| 索引文件未就绪 | `index.faiss/index.pkl` 缺失 | 研报直接失败 | 研报前置检查与 `/api/reports/rag/status` 可视化 |
| 无鉴权 | 当前所有 API 公开 | 安全风险 | 生产必须加鉴权与限流 |
| 依赖版本未完全锁定 | Python requirements 有未 pin 包 | 复现难 | 版本锁定策略见 2.4 |

## 2) 前后端技术栈明细（版本锁定策略 / CI/CD 工具链）

### 2.1 后端（FastAPI）

- 语言：Python 3.10（Docker 镜像 `python:3.10-slim`）
- 框架：FastAPI、Pydantic、Uvicorn
- RAG：PyPDF2、langchain-text-splitters、FAISS、DashScope
- 配置：python-dotenv（自动从项目根 `.env` 加载）

依赖清单见： [backend/requirements.txt](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/requirements.txt)

### 2.2 前端（Web）

- 语言：TypeScript
- 框架：React 18 + React Router
- 构建：Vite
- 状态：Zustand
- UI：TailwindCSS；图标：lucide-react

依赖清单见： [web/package.json](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/package.json)

### 2.3 Streamlit（对话应用）

- streamlit==1.44.1
- 通过 `AI_QUANT_API_BASE` 指向后端 API（容器内默认 `http://backend:8000`）

依赖清单见： [streamlit_chat/requirements.txt](file:///Users/apple/Desktop/ai_huahua/ai_quant/streamlit_chat/requirements.txt)

### 2.4 版本锁定策略（建议落地标准）

当前状态：

- Python 依赖中存在未 pin 的包（例如 `langchain-community/faiss-cpu/dashscope` 等）
- 前端依赖使用 `package-lock.json`，可复现性相对更好

建议策略：

- 后端：将所有第三方依赖 pin 到明确版本，或引入 `pip-tools` 生成锁文件；Docker 构建只使用锁文件安装
- 前端：持续使用 `npm ci`（已在 [web.Dockerfile](file:///Users/apple/Desktop/ai_huahua/docker/web.Dockerfile) 中落实）

### 2.5 CI/CD 工具链（现状与规划）

现状：仓库内未见已落地的 CI 配置（例如 GitHub Actions/GitLab CI）。

建议最小工具链：

- CI：单元检查（TypeScript `npm run check`）、Lint（`npm run lint`）、后端基础导入检查（启动 FastAPI 并访问 `/api/health`）
- CD：Docker Compose 作为“交付验证基线”；生产环境用镜像仓库 + 部署平台（K8s 或 PaaS）

## 3) 技术架构图（分层 / 组件 / 部署 / 安全，含 UML 2.5 图例）

图源统一约束：

- 统一样式与图例： [\_style.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/_style.puml)
- UML 2.5 图例：包含角色/颜色/关系线型说明（在 legend 中呈现）

架构图（PlantUML 源文件）：

- 分层视图： [arch_layers.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/arch_layers.puml)
- 组件视图： [arch_components.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/arch_components.puml)
- 部署视图： [arch_deployment.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/arch_deployment.puml)
- 安全视图： [arch_security.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/arch_security.puml)

可编辑 DrawIO 源文件（包含 4 个 page：layers/components/deployment/security）：

- [arch.drawio](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/arch.drawio)

## 4) 数据库设计（逻辑/物理/容量/索引/分库分表/备份容灾）

### 4.1 MySQL（业务主库）

物理建表（Compose 初始化脚本）：

- [docker/mysql/init.sql](file:///Users/apple/Desktop/ai_huahua/docker/mysql/init.sql)

ER 图（交底用）：

- [db_mysql_er.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/db_mysql_er.puml)

索引策略（现状）：

- 日线表 `trade_stock_daily`：联合主键 `(stock_code, trade_date)` + `idx_trade_date`
- 新闻表 `trade_stock_news`：联合主键 `(stock_code, published_at)` + `idx_published_at`
- 研报共识 `trade_report_consensus`：联合主键 `(stock_code, broker, report_date)` + `idx_report_date`

容量估算（按常见规模给出可复用口径）：

- `trade_stock_daily`：`N_stock * N_trade_days`
  - 以 5000 只股票、250 个交易日估算：约 125 万行/年
- `trade_stock_news`：受数据源影响较大，按 1~20 条/股/日浮动；建议独立归档策略

分库分表规则（规划建议）：

- `trade_stock_daily` 按 `trade_date` 做月分区或按年份分表（`trade_stock_daily_YYYY`）
- `trade_stock_news` 按 `published_at` 做月分区并设置冷热分层（近 90 天热数据，历史归档）

备份与容灾（建议）：

- 本地验证：MySQL 数据 volume 定期快照
- 生产建议：主从复制 + 每日全量 + binlog 增量；跨可用区备份；恢复演练制度化

### 4.2 SQLite（RAG 元数据库）

默认位置：

- `.ai_quant/reports_rag/documents.db`

建表与索引实现：

- [rag.py:\_init_db](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/reports/rag.py#L61-L108)

ER 图（交底用）：

- [db_rag_sqlite_er.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/db_rag_sqlite_er.puml)

WAL 配置：

- `PRAGMA journal_mode=WAL` 与 `PRAGMA synchronous=NORMAL`，实现见 [rag.py:\_connect_db](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/services/reports/rag.py#L53-L58)

## 5) 信息架构图（用户旅程 / 功能地图 / 导航结构 / 权限矩阵）

PlantUML 图源：

- 用户旅程： [ia_user_journey.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/ia_user_journey.puml)
- 功能地图： [ia_function_map.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/ia_function_map.puml)
- 导航结构： [ia_navigation.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/ia_navigation.puml)
- 权限矩阵： [ia_permission_matrix.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/ia_permission_matrix.puml)

说明：

- 当前系统默认不做鉴权，权限矩阵以“规划交付/企业化部署”为目标，用于评审与后续实现落地

## 6) 接口文档（REST & GraphQL：模型/错误码/鉴权/Mock/变更记录）

### 6.1 REST（FastAPI）

路由总入口：

- 应用注册： [app.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/app.py#L28-L50)
- 路由目录： [api/](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api)

核心接口（节选，覆盖 `.ai_quant` 相关链路）：

- 健康检查：`GET /api/health`
- 股票搜索（研报选股器使用）：`GET /api/stocks?q=...&limit=...`（实现位于 services/charles，供前端复用）
- 研报任务：
  - `GET /api/reports/tasks`：列表（带 q/日期过滤）
  - `POST /api/reports/tasks`：创建（入参 `model + stock_codes`）
  - `GET /api/reports/tasks/{task_id}/view`：查看 Markdown 或错误文本
  - `DELETE /api/reports/tasks/{task_id}`：删除任务记录
- RAG：
  - `GET /api/reports/rag/status`
  - `POST /api/reports/rag/ingest`：入库 + 构建索引
  - `GET /api/reports/rag/query`

研报端点实现见： [reports.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/reports.py)

### 6.2 错误码体系（约定）

当前以 HTTP 状态码 + `detail`/文本响应为主：

- 400：参数错误（例如未知 model、缺少 stock_codes）
- 404：资源不存在（任务 ID 不存在）
- 409：任务尚未就绪（`report not ready`）
- 500：服务端错误（任务失败时 `/view` 直接返回错误文本）

### 6.3 鉴权流程（现状与要求）

现状：

- 当前 API 未实现鉴权，仅做 CORS 限制（见 [app.py:CORS](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/app.py#L31-L37)）

生产要求（规划）：

- 统一鉴权（JWT/OAuth2），并在安全视图中标注鉴权点
- 对 `.ai_quant` 的落盘数据做访问隔离（至少按租户/用户隔离输出目录）

### 6.4 Mock 规则（用于前端联调与评审验收）

为了保证交付评审可重复，建议 Mock 采用“固定输入 -> 固定输出”的确定性规则：

- 对 `GET /api/reports/tasks`：固定返回 2~3 个任务（waiting/running/success/failed 各 1）
- 对 `GET /api/reports/tasks/{id}/view`：success 返回稳定 Markdown；failed 返回稳定错误文本
- 对 `GET /api/stocks`：按 q 前缀匹配固定股票列表

落地方式（任选其一）：

- 前端 MSW（mock service worker）拦截 `/api/*`
- 或后端增加 `AI_QUANT_MOCK=1` 模式（通过路由返回固定响应）

### 6.5 GraphQL（规划：Schema 源文件交付）

当前仓库已提供 GraphQL Schema 源文件，用于接口评审与未来落地：

- [schema.graphql](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/api/graphql/schema.graphql)

说明：

- 目前未提供 GraphQL 运行时服务与 `/graphql` 端点实现；该部分属于“协议层规划交付”

### 6.6 变更记录（可审计口径）

- 2026-05-08：研报输出目录归一到 `repo_root/.ai_quant/report_outputs`，并增加研报成功落盘 `<task_id>.md`（实现见 [reports.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/ai_quant_api/api/reports.py#L172-L235)）

## 7) 前端交互说明（流程/状态/可访问性/性能/埋点）

### 7.1 页面流程图

- 智能研报页面流程： [ui_reports_flow.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/ui_reports_flow.puml)

### 7.2 组件状态图

- 研报选股器状态机： [ui_reports_picker_state.puml](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/diagrams/ui_reports_picker_state.puml)

### 7.3 可访问性标准（建议验收项）

- 所有可点击元素具备可聚焦性与键盘可操作（Tab/Enter/Escape）
- 弹层/下拉具备 Esc 关闭逻辑（研报选股器已实现 `Escape` 关闭）
- 输入框具备可读 placeholder 与可见 label

### 7.4 性能指标（建议验收项）

- 研报任务轮询：当前 `/reports` 以 1.5s 轮询刷新任务列表（实现见 [Reports.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/pages/Reports.tsx#L70-L76)）
- 股票搜索：150ms 防抖 + 1200ms 超时（实现见 [Reports.tsx](file:///Users/apple/Desktop/ai_huahua/ai_quant/web/src/pages/Reports.tsx#L78-L116)）

### 7.5 埋点方案（规划）

建议埋点维度（不含具体实现）：

- 研报：创建任务、选择模型、选股次数、任务成功/失败、view 打开次数
- RAG：ingest 次数、索引构建耗时、query 召回 topK
- 运行时：`.ai_quant` 写入失败次数（权限/磁盘/空间）

## 8) Docker Compose 一键本地验证环境（可运行基线）

交付目标：

- 在无本地 Python/Node 环境依赖的情况下，使用 Docker Compose 一键启动：
  - MySQL（初始化最小表结构）
  - backend（FastAPI）
  - web（Vite dev server，/api 代理到 backend）
  - streamlit（对话应用）
- 将 `.ai_quant` 挂载为 volume，使研报日志/产物/RAG 数据可持久化

Compose 文件：

- [docker-compose.yml](file:///Users/apple/Desktop/ai_huahua/docker-compose.yml)

验收口径（最小集合）：

- `GET http://localhost:8000/api/health` 返回 200
- `http://localhost:5173/` 页面可打开，并能访问 `/reports` 页面
- 研报任务创建后，`.ai_quant/reports_worker.log` 有日志追加，且成功时生成 `.ai_quant/report_outputs/<task_id>.md`

## 9) 团队评审 Checklist

评审清单文件：

- [checklist.md](file:///Users/apple/Desktop/ai_huahua/ai_quant/docs/tech_handover/checklist.md)

