# ai_huahua

本仓库包含“项目落地代码 + 课程代码（已统一迁移到 lesson/）”。

## 目录导航

- `ai_quant/`：统一 AI 量化系统默认入口（FastAPI + React + Streamlit Chat）
- `charles/`：数字员工情报官（采集 / 清洗 / 落库 / Web 控制台）
- `zoe/`：数字员工分析师（指标 / 信号 / 选股 / 回测）
- `ceo/`：CEO 控制台（整合型 Web 工作台：实盘/模拟盘、回测、晨会、投研对话等）
- `ethan/`：Ethan（交易官：研究/执行相关的全栈模块）
- `kris/`：Kris（风控官：风控相关的全栈模块）
- `lesson/`：课程周代码（`lesson/week1` ~ `lesson/week11`）

数据库建库建表脚本（MySQL 8.0+）：`huahua_trade_schema_show_create.sql`

## Code Wiki

- 总览 Wiki：`CODE_WIKI.md`
- Charles Wiki：`charles/CODE_WIKI.md`
- Zoe Wiki：`zoe/CODE_WIKI.md`

## 默认入口与保留策略

- 默认入口已切换到 `ai_quant/`，用于日常开发、联调和演示。
- 原 `charles/`、`zoe/`、`ethan/`、`kris/`、`ceo/` 工程保留，用于迁移期对照与回归。
- 若无特殊说明，请优先使用统一系统，不再以原子系统作为默认启动入口。

## Charles（数字员工情报官）

项目代码位于：`charles/`

- 项目说明与启动：`charles/README.md`
- 后端（FastAPI）：`charles/api/`
- 前端（React Web 控制台）：`charles/web/`
- 一键启动脚本：`charles/scripts/`

## Zoe（数字员工分析师）

项目代码位于：`zoe/`

- 项目说明与启动：`zoe/README.md`
- 后端（FastAPI + 内置 Web 模板）：`zoe/zoe/app/`

## CEO 控制台

项目代码位于：`ceo/`

- 项目说明与启动：`ceo/README.md`
- 入口：`ceo/app.py`

## Ethan（交易官）

项目代码位于：`ethan/`

- 后端：`ethan/backend/`（入口：`ethan/backend/run_server.py`）
- 前端：`ethan/frontend/`

## Kris（风控官）

项目代码位于：`kris/`

- 后端：`kris/api/`（入口：`kris/api/run_server.py`）
- 前端：`kris/web/`

## 课程代码（lesson）

课程周代码已从仓库根目录迁移至 `lesson/`，按周组织：

- `lesson/week1` ~ `lesson/week11`
