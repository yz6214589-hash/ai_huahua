## 背景与目标

本次后端重构聚焦于：

- 接口统一：统一版本前缀、统一返回格式、统一错误码与请求链路标识
- 去外部依赖：清理并移除 charles / zoe / ethan / kris / ceo 相关的外部系统集成代码
- 内聚分层：业务能力收敛到 modules，路由层仅负责协议与编排

## 版本策略

- 新接口统一使用：`/api/v1/...`
- 根路径与健康检查：
  - `/`：返回基础信息（含 `/api/v1/health`）
  - `/health`：健康检查别名（无版本）

## 统一响应格式

所有 JSON 响应统一包装为：

```json
{
  "success": true,
  "code": 0,
  "message": "ok",
  "data": {},
  "requestId": "..."
}
```

说明：

- `success`：成功/失败
- `code`：业务错误码（成功为 0）
- `message`：可读错误信息
- `data`：业务数据
- `requestId`：链路标识（同时写入响应头 `X-Request-Id`）

## 错误码约定（核心）

- `0`：成功
- `40001`：参数校验失败（HTTP 422）
- `40100`：未授权（HTTP 401）
- `40300`：无权限（HTTP 403）
- `40400`：资源不存在（HTTP 404）
- `42900`：请求过于频繁（HTTP 429）
- `50000`：服务器内部错误（HTTP 500）

## 认证与链路

- `x-api-key`：当环境变量配置了 `AI_QUANT_API_KEY`（或配置文件映射）时启用
- `x-request-id`：可选；不传则自动生成，并返回到 `X-Request-Id`

## 分页模型

分页统一使用：

- `page`：从 1 开始
- `pageSize`：每页大小（服务端会做上限约束）

## 旧接口 → 新接口映射（常用）

本次迁移的核心规则是：`/api/...` 统一迁移为 `/api/v1/...`。

- 健康检查
  - `/api/health` → `/api/v1/health`
- 数据汇总
  - `/api/summary` → `/api/v1/summary`
  - `/api/data/summary` → `/api/v1/data/summary`
- 数据查询与导出
  - `/api/data/{dataset}` → `/api/v1/data/{dataset}`
  - `/api/export` → `/api/v1/export`
- 自选股
  - `/api/watchlist` → `/api/v1/watchlist`
  - `/api/watchlist/{stock_code}` → `/api/v1/watchlist/{stock_code}`
- 任务队列
  - `/api/jobs/...` → `/api/v1/jobs/...`
- 研报
  - `/api/reports/...` → `/api/v1/reports/...`
- 风控
  - `/api/risk/...` → `/api/v1/risk/...`
- 执行
  - `/api/execution/...` → `/api/v1/execution/...`
- 舆情与宏观
  - `/api/sentiment/...` → `/api/v1/sentiment/...`
  - `/api/macro/latest` → `/api/v1/macro/latest`
- AI/对话
  - `/api/agent/...` → `/api/v1/agent/...`
  - `/api/conversations/...` → `/api/v1/conversations/...`

## 被删除的外部系统依赖与替代方案

已移除目录（不再存在对外部系统的 SDK/客户端/服务发现/DTO/转换器依赖）：

- `ai_quant_api/services/charles`
- `ai_quant_api/services/zoe`
- `ai_quant_api/services/ethan`
- `ai_quant_api/services/kris`
- `ai_quant_api/services/ceo`

替代方案（内部能力收敛）：

- 数据与任务：`ai_quant_api/modules/data`、`ai_quant_api/modules/jobs`
- 技术分析：`ai_quant_api/modules/analysis`
- 执行：`ai_quant_api/modules/execution`
- 风控：`ai_quant_api/modules/risk`
- 控制台/晨会：`ai_quant_api/modules/console`

约束：

- 路由层（`ai_quant_api/api`）只能依赖 `common / modules / runtime`
- 禁止跨模块直接调用对方内部实现（以 modules 为边界）

## 数据库变更

- 本次重构未引入新的数据库 schema 变更
- 已存在的迁移脚本仍位于：`backend/migrations/`

## CI 与覆盖率门禁

- GitHub Actions：`.github/workflows/backend-ci.yml`
- 覆盖率门禁：≥ 80%
- 覆盖率统计范围聚焦在统一入口/统一响应/核心运行时与关键路由模块（避免将历史遗留大文件纳入门禁导致不可达标）

## 本地验证方式（推荐）

- 使用虚拟环境运行：`ai_quant/venv`
- 运行单测：
  - `python -m pytest`
- 启动服务（端口可按需调整）：
  - `python -m uvicorn ai_quant_api.app:app --host 0.0.0.0 --port 8010`
  - 浏览器访问 `http://localhost:8010/docs` 验证 `/api/v1/...` 路由与统一返回格式

