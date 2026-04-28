# Charles 最小修复记录（Critical / Major）

日期：2026-04-22  
目标：在不改业务逻辑的前提下，用最小改动修复测试阶段识别的 Critical / Major 缺陷，并补齐验证闭环。  
范围：后端 FastAPI + 前端 React（仅与缺陷直接相关的最小改动）。

---

## 1. 背景与问题概览

在全栈测试中发现以下高优先级问题：

- **Critical**：`POST /api/jobs/run` 返回 500，导致“手动触发任务运行 + 生成运行记录”的核心链路不可用。
- **Major**：股票检索依赖 `trade_stock_master`，当主数据不全时出现：
  - `/api/stocks?q=600519` 搜不到（甚至出现请求超时/前端无候选）。
  - `/api/stocks?codes=...` 批量映射部分 name 为 `null`，自选股“手动添加”无法覆盖常见股票。
- **Major/Minor**：`/api/stock/{code}/fundamentals` 返回 `stock_name=null`，与 snapshot 显示不一致，影响详情页信息完整性。
- **Major（体验）**：Jobs 页面轮询刷新会清空错误提示，导致“运行失败”用户难以感知与定位。

对应测试原始记录见：  
- [CHARLES_全栈测试报告_2026-04-22.md](file:///c:/Users/40320/Desktop/geek_python_study/huahua/ai_huahua/charles/CHARLES_%E5%85%A8%E6%A0%88%E6%B5%8B%E8%AF%95%E6%8A%A5%E5%91%8A_2026-04-22.md)

---

## 2. 修复策略（“最小修复、不改业务逻辑”解释）

本次修复坚持以下边界：

- **不改变数据来源优先级与业务流程**（例如采集逻辑、指标计算方式不动）。
- **只做兜底、回退与一致性补全**：
  - 避免因配置空值/边界值导致的 500。
  - 主数据不全时，为“检索/展示”提供合理回退路径（不等于改造数据同步策略）。
  - 补齐返回字段的一致性（如 `stock_name`）。
- **优先保证关键链路可用与可观测**（错误信息可见、运行记录可落盘）。

---

## 3. 修复记录（按缺陷编号）

### 3.1 BUG-API-01（Critical）：jobs/run 500（运行记录无法写入）

**问题现象**
- `POST /api/jobs/run` 返回 500。
- 运行记录未生成，UI 历史运行记录长期为空。

**根因分析**
- `Settings.job_store_dir` 读取环境变量 `CHARLES_JOB_STORE_DIR`。
- 当该环境变量存在但值为空字符串时，`job_store_dir` 变为 `''`。
- 随后 `os.makedirs('')` 触发 `FileNotFoundError`，导致接口 500。

**最小修复**
- 对 `CHARLES_JOB_STORE_DIR` 做 `.strip()` 校验：为空/缺失时统一回退到默认路径 `./.charles/job_runs`。

**改动文件**
- [config.py](file:///c:/Users/40320/Desktop/geek_python_study/huahua/ai_huahua/charles/api/charles_api/config.py)

**验证结果**
- `POST /api/jobs/run` 返回 200，生成 `runId`。
- `GET /api/jobs/runs?domain=calendar&limit=...` 能看到 `running`，随后变为 `success/failed` 并包含统计字段。

---

### 3.2 BUG-API-02/03（Major）：stocks 搜索/映射在 master 不全时不可用

**问题现象**
- `/api/stocks?q=600519` 无结果（部分环境出现请求耗时长/前端候选为空）。
- `/api/stocks?codes=002410,600519` 返回 `600519` 的 `name=null`。
- UI 自选股“手动添加”输入 `600519` 时出现“无匹配结果”。

**根因分析**
- 当前搜索逻辑一旦检测到 `trade_stock_master` 有数据（`has_master=true`），就会优先只查 master：
  - master 不全时，部分代码/名称查不到。
  - 纯代码搜索用 `LIKE` 走大表/索引不友好路径时，容易触发慢查询风险。

**最小修复（不改业务：仅增加回退）**
1. **纯代码查询走精确匹配**  
   - 当 `q` 看起来像股票代码（6位数字或已带 `.SZ/.SH`）时：
     - 先查 master 精确命中则直接返回；
     - master 未命中则回退到 `trade_stock_daily` 按 `stock_code` 精确查最新一条（避免 `LIKE` + `DISTINCT` 造成的性能与超时风险）。
2. **批量 codes 映射补全**  
   - 先查 master 得到 `code->name` 映射；
   - 对缺失的 code，回退到 `trade_stock_daily` 查 name 进行补齐（仅补 name，不改 code）。
3. **模糊查询回退**  
   - master 模糊搜索无结果时，再回退到 `trade_stock_daily`（提升可用性）。

**改动文件**
- [app.py](file:///c:/Users/40320/Desktop/geek_python_study/huahua/ai_huahua/charles/api/charles_api/app.py)

**验证结果**
- `GET /api/stocks?q=600519&limit=5` 返回 `600519.SH 贵州茅台`。
- `GET /api/stocks?codes=002410,600519` 两只股票 name 均可返回。
- 前端自选股“手动添加”输入 `600519` 能看到候选 `600519.SH 贵州茅台`。

---

### 3.3 BUG-API-04（Major/Minor）：fundamentals 返回 stock_name 为空

**问题现象**
- `/api/stock/{code}/fundamentals` 返回 `stock_name: null`，但 `/snapshot` 往往能返回名称。

**根因分析**
- fundamentals 接口仅使用 snapshot 的 `stock_name`，未进行兜底补全。

**最小修复**
- 返回时使用：`name = snap.stock_name or _get_stock_name(code)`，保证与 snapshot 行为一致。

**改动文件**
- [app.py](file:///c:/Users/40320/Desktop/geek_python_study/huahua/ai_huahua/charles/api/charles_api/app.py)

**验证结果**
- `GET /api/stock/002410/fundamentals` 返回 `stock_name: 广联达`。

---

### 3.4 BUG-UI-03（Major，体验）：Jobs 页错误提示被轮询刷新覆盖

**问题现象**
- 运行失败后错误提示可能被 1.5s 的轮询刷新清掉，用户感知为“点了没反应”。

**根因分析**
- `load()` 在轮询时每次都会 `setErr(null)`，会覆盖刚产生的错误。

**最小修复**
- `load(opts?: { silent?: boolean })`：当 `silent=true`（轮询）时不清空 err，仅在用户主动刷新或主动操作触发的 load 时清空。

**改动文件**
- [Jobs.tsx](file:///c:/Users/40320/Desktop/geek_python_study/huahua/ai_huahua/charles/web/src/pages/Jobs.tsx)

**验证结果**
- 当接口报错时，错误信息可持续显示，不会被轮询立刻覆盖。

---

## 4. 整体性分析（架构与数据一致性视角）

### 4.1 jobs/run 的“可用性”与“可观测性”

该链路的核心是：

- **运行请求可受理**：API 不应因“可选配置”空值导致 500。
- **运行记录可落盘**：否则 UI 的“历史运行记录/运行详情”全部失效。
- **后台任务异步执行**：保持原有 BackgroundTasks 机制不变，本次只修复“写运行记录路径”的稳定性。

### 4.2 stocks 搜索的“主数据不完备”容错

系统存在两类数据源：

- `trade_stock_master`：用于“代码↔名称”的稳定映射（理想状态应全覆盖）。
- `trade_stock_daily`：天然包含大量 code/name（即使 master 不全，仍可作为 fallback）。

本次改动的本质是：**避免“master 部分存在”导致系统误判“master 完备”**，通过“精确匹配 + 回退”保证检索可用，且避免在大表上做高成本模糊查询造成超时。

### 4.3 返回字段一致性

同一股票在多个接口中展示名称：

- snapshot、fundamentals、watchlist、stocks 搜索

本次将 fundamentals 的 name 逻辑与 snapshot 对齐，属于典型的“读模型一致性补全”，不改变业务数据。

---

## 5. 回归验证清单（本次修复已覆盖）

- jobs/run：`POST /api/jobs/run` 200；`GET /api/jobs/runs` 可见记录并可完成。
- stocks：
  - `GET /api/stocks?q=600519` 能返回结果；
  - `GET /api/stocks?codes=002410,600519` name 可补齐；
  - UI 自选股“手动添加”输入 600519 有候选。
- fundamentals：返回 `stock_name` 不为空。
- Jobs UI：错误提示不被轮询覆盖。

---

## 6. 未纳入本次“最小修复”的问题（说明）

- `POST /api/stocks/sync?scope=all` 仍可能因外部网络/数据源不稳定报错（例如 RemoteDisconnected）。  
  该问题属于**外部依赖稳定性**，要彻底改善通常需要：重试/分片/断点续传/限流/落库策略等，已经超出“最小修复、不改业务逻辑”的范围。

---

## 7. 变更清单（方便 code review）

- 后端
  - [config.py](file:///c:/Users/40320/Desktop/geek_python_study/huahua/ai_huahua/charles/api/charles_api/config.py)：job_store_dir 空字符串兜底
  - [app.py](file:///c:/Users/40320/Desktop/geek_python_study/huahua/ai_huahua/charles/api/charles_api/app.py)：stocks 搜索回退、codes 补全、fundamentals 补齐名称
- 前端
  - [Jobs.tsx](file:///c:/Users/40320/Desktop/geek_python_study/huahua/ai_huahua/charles/web/src/pages/Jobs.tsx)：轮询 silent 模式不清空错误

