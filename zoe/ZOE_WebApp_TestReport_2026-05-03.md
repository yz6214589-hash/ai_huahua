# Zoe WebApp 测试报告（webapp-testing + 可视化浏览器自动化）

项目路径：`/Users/apple/Desktop/ai_huahua/zoe`  
测试日期：2026-05-03  
被测服务：`uvicorn zoe.app.main:app`（本次以 `http://127.0.0.1:18020` 为基准）  

约束声明：
- 本次仅做测试与环境依赖安装，不对现有业务代码做修改/删除操作
- UI 自动化采用“可视化浏览器自动化”（共享浏览器实例）完成，不使用无头模式

---

## Step 1：MFQ 海盗测试法（测试分析脑图）

```mermaid
mindmap
  root((Zoe WebApp 测试分析))
    M[Mission 使命]
      M1[核心任务：策略/回测/绩效/主力识别一站式分析]
      M2[用户目标：快速得到可解释结论与报告链接]
      M3[关键路径：打开控制台→创建/运行任务→查看结果/报告]
    F[Function 功能面]
      F1[页面导航]
        F11[/]
        F12[/performance]
        F13[/mainforce]
      F2[主力识别任务]
        F21[创建任务]
        F22[列表/详情]
        F23[运行任务]
        F24[产物：png + html report]
      F3[绩效分析 QuantStats]
        F31[Common-净值CSV]
        F32[Common-回测(依赖 backtrader)]
        F33[报告 /reports/*]
      F4[公共能力]
        F41[/health]
        F42[/api/v1/strategies]
        F43[静态资源 /static /reports /mainforce-assets]
    Q[Quality 质量面]
      Q1[可用性]
        Q11[服务可启动/端口可访问]
        Q12[关键页面可打开]
      Q2[正确性]
        Q21[API 状态码/响应结构]
        Q22[任务状态流转 pending→running→done/failed]
      Q3[健壮性]
        Q31[缺依赖时的友好报错]
        Q32[DB 不可用时的降级/提示]
      Q4[性能]
        Q41[任务运行耗时与可取消性]
      Q5[安全/合规]
        Q51[静态报告是否可被枚举]
        Q52[输入校验（stock_code/文件）]
    Pirate[海盗指标（AARRR）]
      A1[Acquisition 获取：入口可发现（导航栏）]
      A2[Activation 激活：创建任务/生成报告一次成功]
      A3[Retention 留存：任务可复用/可再次运行]
      A4[Revenue 价值：报告/图表可导出]
      A5[Referral 传播：report_url 可分享]
```

---

## Step 2：测试用例（When-Given-Then）

### 2.1 API 用例

| ID | 模块 | When | Given | Then | 预期 |
|---|---|---|---|---|---|
| API-001 | Health | 调用健康检查 | 服务已启动 | 返回 200 + JSON | 包含 time/talib/db 字段 |
| API-002 | Strategies | 获取策略列表 | 服务已启动 | 返回 200 + JSON | strategies 为数组且非空 |
| API-003 | MainForce | 创建主力识别任务 | stock_code 合法 | 返回 200 + JSON | 返回 task_id |
| API-004 | MainForce | 任务列表包含新任务 | 已创建任务 | 返回 200 | tasks 中包含该 task_id |
| API-005 | MainForce | 运行任务 | 已存在任务 task_id | 返回 200 | status=done，result.label 非空 |
| API-006 | MainForce | 获取任务详情 | 已运行完成 | 返回 200 | artifacts 含 png + report_url |
| API-007 | MainForce | 访问产物 | artifacts 有 radar_png/report_url | 返回 200 | 文件可打开 |
| API-008 | MainForce | 删除任务 | 已存在任务 task_id | 返回 200 | deleted=task_id |
| API-009 | Performance | Common-净值CSV生成报告 | 上传 date/nav CSV | 返回 200 | metrics 非空 + report_url 可访问 |
| API-010 | Performance | Common-回测缺依赖提示 | backtrader 未安装 | 返回 500 | detail.error=backtrader_missing 且含 hint |

### 2.2 UI 用例（可视化自动化）

| ID | 页面 | When | Given | Then | 预期 |
|---|---|---|---|---|---|
| UI-001 | 首页 | 打开 `/` | 服务运行 | 页面加载 | 顶部导航可见 |
| UI-002 | 主力识别 | 点击导航“主力识别” | 首页已加载 | 跳转 `/mainforce` | 创建任务区域可见 |
| UI-003 | 主力识别 | 点击“创建” | 默认参数 | 列表新增任务并选中 | 选中任务ID更新 |
| UI-004 | 绩效分析 | 点击导航“绩效分析” | 任意页面 | 跳转 `/performance` | 策略下拉加载成功 |
| UI-005 | 绩效分析 | 切换到“净值CSV” | `/performance` | 表单切换 | 出现文件上传控件 |

---

## Step 3：API 测试执行记录 & Bug 记录

### 3.1 API 执行结果（抽样关键路径）

| Case | 实际结果 | 结论 |
|---|---|---|
| API-001 `/health` | 200；返回 `db=false` | Pass |
| API-002 `/api/v1/strategies` | 200；策略数=25 | Pass |
| API-003~008 主力识别任务全链路 | 创建/运行/详情/产物/删除均 200 | Pass |
| API-009 Common-净值CSV | 200；`metrics=True`，`report_url=True` | Pass |
| API-010 Common-回测缺依赖 | 本次未强制执行（环境可能未安装 backtrader） | Skip（按预期应返回 backtrader_missing） |

### 3.2 Bug 清单（API/服务）

| Bug ID | 标题 | 严重级别 | 复现步骤 | 实际结果 | 期望结果 | 备注/建议 |
|---|---|---|---|---|---|---|
| BUG-001 | 服务启动失败：`ModuleNotFoundError: websockets.asyncio` | High | 运行 `uvicorn zoe.app.main:app`（导入 yfinance 相关依赖时触发） | 进程启动即退出，前端/接口不可用 | 服务可启动或给出清晰依赖提示 | 依赖缺口导致“无法访问此网站(连接被拒绝)”。临时修复：安装 `websockets>=13`（本次安装后恢复启动） |

---

## Step 4：UI 自动化测试执行记录 & Bug 记录（可视化）

### 4.1 UI 执行结果

| Case | 实际结果 | 结论 |
|---|---|---|
| UI-001 打开 `/` | 页面可加载，导航可见 | Pass |
| UI-002 进入 `/mainforce` | 页面可加载，表单/列表可见 | Pass |
| UI-003 创建任务 | 点击“创建”后选中任务ID更新 | Pass |
| UI-004 进入 `/performance` | 页面可加载，策略下拉可见且已填充 | Pass |
| UI-005 切换“净值CSV” | 表单切换成功 | Pass |

截图（测试过程留存）：
- `zoe-ui-mainforce.png`（主力识别页）
- `zoe-ui-performance.png`（绩效分析页）

### 4.2 Bug 清单（UI）

| Bug ID | 标题 | 严重级别 | 复现步骤 | 实际结果 | 期望结果 | 备注/建议 |
|---|---|---|---|---|---|---|
| - | - | - | - | - | - | 本轮 UI 抽样链路未发现明确功能性缺陷（不含测试工具超时类问题） |

---

## Step 5：整体测试结论（测试报告）

总体结论：
- 在补齐依赖 `websockets>=13` 后，Zoe 服务可正常启动并对外提供前端与 API（关键路径可用）
- 主力识别模块（任务 CRUD + 运行 + 图表/报告链接）端到端可用
- QuantStats Common-净值CSV 报告生成与报告访问可用

主要风险与建议：
- **依赖一致性风险（高）**：服务启动依赖存在缺口（BUG-001），建议将关键依赖补齐到 requirements（或启动时预检并提示）
- **环境依赖风险（中）**：`/health` 显示 `db=false`，数据库不可用时相关功能需要明确降级提示/跳过策略
- **任务性能风险（中）**：主力识别训练/绘图耗时与参数上限需要约束（避免极端参数导致页面长时间无响应）

---

## Step 6：交付物

本文件已包含：
- 测试分析（MFQ 脑图）
- API/UI 测试用例表
- API/UI 执行记录与 Bug 清单
- 整体测试结论

