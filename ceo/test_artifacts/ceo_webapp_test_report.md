# 控制台CEO（ceo）测试报告

## 基本信息
- 项目路径：[ceo](file:///Users/apple/Desktop/ai_huahua/ceo)
- 测试目标：对 Web 工作台的核心页面与核心 API 做冒烟/回归验证，输出分析、用例、执行记录与问题清单
- 被测服务地址：http://127.0.0.1:7865
- 测试时间：2026-05-03

## Step 1：测试分析（MFQ 海盗测试法）

### 说明
- **M（Main Flow）主流程**：用户从进入工作台到完成关键操作链路
- **F（Function）功能点**：各模块功能是否按预期可用（导航、接口、交互、数据展示）
- **Q（Quality）质量属性**：稳定性、性能感知、可用性、安全/权限边界（本项目当前无登录鉴权）

### 分析脑图（mermaid）
```mermaid
mindmap
  root((CEO 控制台测试 MFQ))
    M(主流程 Main Flow)
      M1(进入工作台 / -> /live/sim)
      M2(查看系统状态 /system + 触发健康检查)
      M3(回测入口 /backtest: 参数输入->运行->结果展示)
      M4(晨会入口 /morning: 读缓存->触发流程(SSE))
      M5(投研对话 /chat: iframe加载->对话(依赖Key))
    F(功能 Function)
      F1(导航栏 Tab 切换与 active 高亮)
      F2(系统健康接口 /api/system/health)
      F3(实盘监控接口 /api/live/*)
      F4(回测接口 /api/backtest/*)
      F5(晨会接口 /api/morning/*)
      F6(页面依赖静态资源 /static/css/main.css /static/js/main.js)
    Q(质量 Quality)
      Q1(可用性：页面加载不阻塞、按钮可点击、错误可见)
      Q2(稳定性：接口 200/可读错误；前端不空白不报致命错)
      Q3(依赖健壮性：缺行情/数据库/Key 时的降级提示)
      Q4(性能感知：页面首屏、接口响应时间)
      Q5(安全边界：当前无登录鉴权 -> 需明确部署边界/内网访问)
```

## Step 2：测试用例（Given-When-Then）

### 2.1 API 测试用例
| ID | 场景 | Given | When | Then |
|---|---|---|---|---|
| API-01 | 系统健康检查返回结构正确 | 服务已启动 | GET `/api/system/health` | 返回 200 且 JSON 为数组 |
| API-02 | Live 路由探活 | 服务已启动 | GET `/api/live/ping` | 返回 200 且包含 `ok/module` |
| API-03 | 读取 live_state | 服务已启动 | GET `/api/live/state` | 返回 200 且包含 `trading_status/positions/control` |
| API-04 | 读取模拟盘运行状态 | 服务已启动 | GET `/api/live/sim/status` | 返回 200 且 JSON 为对象 |
| API-05 | 获取策略注册表 | 服务已启动 | GET `/api/live/strategies/registry` | 返回 200 且包含 `groups/flat` |
| API-06 | 回测 ping | 服务已启动 | GET `/api/backtest/ping` | 返回 200 且包含 `mysql_available` |
| API-07 | 回测策略列表 | 服务已启动 | GET `/api/backtest/strategies` | 返回 200 且包含 `groups/list` |
| API-08 | 非法交易状态校验 | 服务已启动 | POST `/api/live/status` `{status:"BAD"}` | 返回 200 且 `ok=false` |
| API-09 | control 缺 field 校验 | 服务已启动 | POST `/api/live/control` `{value:true}` | 返回 200 且 `ok=false` |
| API-10 | 回测 run 空参数校验 | 服务已启动 | POST `/api/backtest/run` `{}` | 返回 200 且 `ok=false` |

### 2.2 UI 测试用例（Playwright，非无头）
| ID | 场景 | Given | When | Then |
|---|---|---|---|---|
| UI-01 | 首页重定向到实盘监控 | 服务已启动 | 打开 `/` | 自动跳转到 `/live/sim` 且可见“实时持仓”卡片标题 |
| UI-02 | 系统状态健康检查可用 | 服务已启动 | 打开 `/system` 点击“健康检查” | 表格出现健康检查结果行 |
| UI-03 | 回测空参数错误可见 | 服务已启动 | 打开 `/backtest` 点击“运行回测” | 出现红色错误提示（参数校验失败） |
| UI-04 | 晨会缓存加载可执行 | 服务已启动 | 打开 `/morning` 点击“用最近缓存” | 页面不报致命错，能完成一次加载动作 |
| UI-05 | 投研对话 iframe 可加载 | 服务已启动 | 打开 `/chat` | 页面存在 iframe（指向 `/gradio-chat/`） |
| UI-06 | 实盘监控帮助弹窗可打开 | 服务已启动 | 打开 `/live/sim` 点击 “?” | 弹出“实盘监控 -- 使用说明” |

## Step 3：API 接口测试执行（记录与 Bug）

### 执行方式
- 脚本：[api_test_run.py](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/api_test_run.py)
- 执行产物：[api_test_result.json](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/api_test_result.json)

### 执行结果汇总
- 用例数：10
- 通过：10
- 失败：0

### Bug / 问题清单（API）
| ID | 严重性 | 描述 | 证据/影响 | 建议 |
|---|---|---|---|---|
| ENV-API-01 | 中 | `xtquant` 缺失导致健康检查中 `xtdata 行情` 为 ERROR | `GET /api/system/health` 返回 `No module named 'xtquant'` | 按部署环境补齐 `xtquant`/行情组件，或在 README 明确必需/可选 |
| ENV-API-02 | 中 | `QMT_PATH` 未配置导致实盘下单不可用（WARN） | 健康检查 `QMT_PATH` 为 WARN | 若需要实盘能力，需按 README 配置并验证 miniQMT 连接 |

## Step 4：UI 测试执行（Playwright，非无头）（记录与 Bug）

### 执行方式
- 脚本：[ui_playwright_test.py](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ui_playwright_test.py)
- 执行产物：[ui_test_result.json](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ui_test_result.json)
- 截图目录：[ui_screens](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ui_screens)
  - [01_live_sim.png](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ui_screens/01_live_sim.png)
  - [02_system_health.png](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ui_screens/02_system_health.png)
  - [03_backtest_validation.png](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ui_screens/03_backtest_validation.png)
  - [04_morning_cache.png](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ui_screens/04_morning_cache.png)
  - [05_chat_iframe.png](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ui_screens/05_chat_iframe.png)
  - [06_live_help.png](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ui_screens/06_live_help.png)

### 执行结果汇总
- 用例数：6
- 通过：6
- 失败：0

### Bug / 问题清单（UI）
本轮 UI 自动化用例均通过，未发现可复现的功能缺陷。

## Step 5：整体测试报告

### 覆盖范围
- 页面冒烟：`/live/sim`、`/system`、`/backtest`、`/morning`、`/chat`
- API 冒烟：`/api/system/*`、`/api/live/*`、`/api/backtest/*`（含参数校验）

### 未覆盖/风险说明
- `/api/morning/stream` 为 SSE 流式流程，受 MySQL 数据与外部依赖影响较大，本轮仅验证“加载缓存”入口未做全流程跑通
- `/api/backtest/run` 正常回测需要 MySQL 历史数据，本轮仅验证参数校验路径与 `ping/strategies` 基础可用
- 项目当前无登录鉴权；部署到非受控网络存在访问风险（建议仅内网/加反向代理鉴权）

### 结论
- Web 工作台核心页面可打开、Tab 导航正常、关键按钮可交互
- 核心 API 冒烟全部通过
- 当前主要风险在运行依赖（行情 `xtquant`、实盘 `QMT_PATH`、数据源 MySQL）是否齐备

## Step 6：最终交付物（单一 Markdown）
本文件即为最终汇总文档：
- [ceo_webapp_test_report.md](file:///Users/apple/Desktop/ai_huahua/ceo/test_artifacts/ceo_webapp_test_report.md)

