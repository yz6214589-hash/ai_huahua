# Code Wiki：Zoe（数字员工分析师）

Zoe 是一个面向 AI 量化交易的“计算服务”。它从 MySQL（默认 `huahua_trade`）读取行情与财务数据，在服务端完成指标计算、信号生成、选股打分与（可选）Backtrader 回测，并提供自带的 Web 控制台（Jinja2 模板，无需 Node）。

项目根目录：[`/Users/apple/Desktop/ai_huahua/zoe`](file:///Users/apple/Desktop/ai_huahua/zoe)

---

## 1. 目录结构

```
zoe/
  zoe/
    app/                       # FastAPI 服务端与核心业务逻辑
      main.py                  # 应用入口 + 全部路由聚合（页面与 API）
      config.py                # Settings + 环境变量加载
      db.py                    # MySQL 访问封装（PyMySQL）
      market_data.py           # 从 MySQL 读取行情/财务数据（DataFrame）
      indicators.py            # 技术指标（SMA/MACD/RSI/BBANDS）
      _talib_fallback.py       # TA-Lib 不可用时的 Pandas/Numpy 实现
      signals.py               # 信号生成与评分逻辑
      screener.py              # 财务筛选 + 多因子打分
      strategy_registry.py     # 策略库（大量策略元信息 + Backtrader 工厂）
      backtest.py              # Backtrader 回测执行与指标汇总
      presets.py               # 策略预设（JSON 文件持久化）
      instances.py             # 策略实例（JSON 文件持久化）
      chan_engine.py           # 缠论字段注入（依赖仓库 week5 的课程代码目录）
      grid_engine.py           # 网格/中枢网格引擎（策略实现中使用）
      web/
        templates/             # Jinja2 模板页（控制台）
        static/                # 静态资源（若存在会自动挂载 /static）
    tests/
      test_signals.py          # 信号生成的单元测试
  requirements*.txt            # Python 依赖（基础/TA-Lib/Backtrader）
  .env.example                 # 环境变量模板
  README.md                    # 使用说明
```

---

## 2. 整体架构

### 2.1 组件关系

Zoe 的结构是典型的“单体服务 + 模块化领域逻辑”：

- **API 层**：FastAPI 路由与请求体模型，集中在 [main.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/main.py)
- **数据访问层（DAL）**：MySQL 连接与查询封装 [db.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/db.py)，以及表读取 [market_data.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/market_data.py)
- **计算层**：
  - 指标： [indicators.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/indicators.py)（优先 TA-Lib；否则走 fallback）
  - 信号： [signals.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/signals.py)
  - 选股： [screener.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/screener.py)
  - 回测： [backtest.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/backtest.py)
- **策略体系**：策略元信息 + 参数 schema + Backtrader 工厂集中在 [strategy_registry.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/strategy_registry.py)
- **本地持久化**：策略预设/策略实例 JSON 文件 [presets.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/presets.py) / [instances.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/instances.py)

### 2.2 数据依赖（MySQL）

Zoe 默认依赖两张核心业务表（通常由仓库的建表 SQL 或上游数据服务写入）：

- `huahua_trade.trade_stock_daily`：日线 OHLCV（Zoe 会在服务端计算 MA/MACD/RSI/布林带用于展示与信号/打分）  
  - 读取入口：`load_daily_ohlcv()` [market_data.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/market_data.py#L28-L68)
- `huahua_trade.trade_stock_financial`：季度财务（用于财务选股）  
  - 读取入口：`latest_financial_row()` [market_data.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/market_data.py#L108-L134)

---

## 3. 运行方式（本地开发/使用）

完整步骤见 [README.md](file:///Users/apple/Desktop/ai_huahua/zoe/README.md)。

### 3.1 环境要求

- Python 3.10+
- MySQL 8.0+（默认库名 `huahua_trade`）

### 3.2 配置（.env）

复制模板并按需修改：

```bash
copy .env.example .env
```

环境变量模板见 [.env.example](file:///Users/apple/Desktop/ai_huahua/zoe/.env.example)：

- 服务：`ZOE_HOST`（默认 `127.0.0.1`）、`ZOE_PORT`（默认 `8010`）
- MySQL：`DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD`
- 本地 JSON：`PRESETS_PATH`、`INSTANCES_PATH`

配置加载实现见 `load_settings()`：[config.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/config.py#L24-L49)

### 3.3 安装依赖与启动

- 基础依赖：

```bash
pip install -r requirements.txt
```

- 可选：启用 TA-Lib（指标优先使用原生 TA-Lib）：

```bash
pip install -r requirements-talib.txt
```

- 可选：启用 Backtrader 回测：

```bash
pip install -r requirements-backtest.txt
```

启动：

```bash
python -m zoe.app.main
```

默认访问：

- Web 控制台：`http://127.0.0.1:8010/`
- 健康检查：`http://127.0.0.1:8010/health`

---

## 4. 主要模块职责（按领域）

### 4.1 API 与页面（main.py）

[main.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/main.py) 将“页面路由 + API 路由 + 请求模型 + 参数校验”集中在同一处，便于单体应用快速迭代。

**页面路由（Jinja2 模板）**

- `GET /`：主页
- `GET /signals`：信号页面
- `GET /screener`：选股页面
- `GET /strategies`：策略库页面
- `GET /backtest`：回测页面

**API 路由分组（核心）**

- 系统：
  - `GET /health`：返回 DB 连通性、talib 后端信息（native/fallback）等
- 股票/指标：
  - `GET /api/v1/stocks/sample`：返回一批股票代码（来自 `trade_stock_daily`）
  - `GET /api/v1/technical/series`：返回 OHLCV + 指标序列
- 信号：
  - `GET /api/v1/signals`：返回 BUY/SELL 信号 + 评分 + 原因 + 快照
- 选股：
  - `POST /api/v1/screener/financial`：财务阈值筛选
  - `POST /api/v1/screener/factors`：多因子打分 TopN
- 策略库与本地持久化：
  - `GET /api/v1/strategies`：列出策略元信息（含 params_schema/default_params/flags）
  - `GET/POST/DELETE /api/v1/strategies/presets*`：策略预设管理
  - `GET/POST/DELETE /api/v1/strategy-instances*`：策略实例管理（带参数强制类型校验）
- 回测：
  - `POST /api/v1/backtest/run`：运行 Backtrader 回测（缺依赖会明确提示安装方式）

### 4.2 配置（config.py）

[config.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/config.py)

- `Settings`：集中描述服务与 DB 配置项
- `load_settings()`：加载 `.env`/环境变量并给出默认值（包含 presets/instances JSON 路径）

### 4.3 MySQL 访问封装（db.py）

[db.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/db.py)

- `_connect(settings)`：建立 PyMySQL 连接（DictCursor + utf8mb4）
- `db_conn(settings)`：contextmanager 管理连接生命周期
- `fetch_all(settings, sql, params)`：返回 `list[dict]`
- `fetch_one(settings, sql, params)`：返回 `dict | None`

### 4.4 数据读取（market_data.py）

[market_data.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/market_data.py)

- `_stock_code_candidates(stock_code)`：兼容 `600519` / `600519.SH` / 大小写等候选代码
- `load_daily_ohlcv(settings, stock_code, start, end)`：
  - 从 `trade_stock_daily` 读取并标准化列名为 `open/high/low/close/volume/amount`
  - 输出 `DataFrame`（按交易日升序）
- `list_stock_codes(settings, limit)`：按 `trade_stock_daily` 返回代码列表
- `latest_trade_date(settings, stock_code)`：返回最新交易日
- `latest_financial_row(settings, stock_code)`：从 `trade_stock_financial` 取最新财务行

### 4.5 指标计算（indicators.py / _talib_fallback.py）

- 指标入口：`add_technical_indicators(df)`  
  - 实现：[indicators.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/indicators.py#L32-L55)
  - 输出字段：`ma5/ma10/ma20/ma60/macd_dif/macd_dea/macd_hist/rsi14/boll_upper/boll_mid/boll_lower`
- TA-Lib 适配策略：
  - 优先 `import talib`，失败则导入 [_talib_fallback.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/_talib_fallback.py)
  - 提供 `talib_backend()`/`talib_error()` 供 `/health` 查询当前后端信息

### 4.6 信号生成（signals.py）

[signals.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/signals.py)

- `Signal`：dataclass（`trade_date/signal/score/reasons/snapshot`）
- `generate_signals(tech_df)`：
  - 规则触发：
    - 趋势：价格与 MA20 的“穿越”触发 BUY/SELL
    - 震荡：跌破布林下轨触发 BUY；上穿布林上轨触发 SELL
  - 评分：
    - 基础分 50，叠加趋势突破/上下轨偏离、MACD 柱体、RSI 区间等因素
  - 返回：`list[Signal]`

### 4.7 选股（screener.py）

[screener.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/screener.py)

- `FinancialFilters`：财务阈值结构（ROE、利润率、负债率、现金流等）
- `screen_financial(settings, filters, stock_codes, limit)`：
  - 对股票列表逐个读取最新财务行并过滤
  - 输出包含 `cashflow_to_revenue` 等衍生字段
- `score_factors(settings, stock_codes, as_of, lookback_days, top_n, limit)`：
  - 因子计算 `_calc_factors()`：动量（mom20）、波动（vol20）、成交量（avg_vol20）、RSI、MACD hist
  - 评分：按配置权重做 `rank(pct=True)` 并合成 0-100 分
  - 返回：全量 rows + topN

### 4.8 策略库（strategy_registry.py）

[strategy_registry.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/strategy_registry.py)

- `StrategyMeta`：策略元信息（id、名称、描述、参数 schema、默认参数、策略工厂、flags）
- 参数 schema helper：
  - `_p_int/_p_float/_p_bool/_p_enum/_p_object`：用于生成 UI 友好的参数描述
- `get_strategy_registry()`：返回 `dict[str, StrategyMeta]`（策略 id -> 元信息）
  - 定义位置：[strategy_registry.py#L1216](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/strategy_registry.py#L1216)
  - 策略工厂函数（示例）：`_make_dual_ma/_make_macd_basic/_make_rsi_basic/_make_boll_basic/...`（内部 `import backtrader`）

### 4.9 策略预设与实例（presets.py / instances.py）

- 预设（Preset）用于保存“策略参数组合”，以 JSON 文件形式持久化：
  - 数据结构与读写：[presets.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/presets.py)
  - 默认路径由 `PRESETS_PATH` 决定（见 [.env.example](file:///Users/apple/Desktop/ai_huahua/zoe/.env.example)）
- 实例（StrategyInstance）用于保存“用户创建的策略实例”（带名称与参数）：
  - 数据结构与读写：[instances.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/instances.py)
  - `load_instances()` 会调用 `normalize_instances()`：确保 instance_id 连续且可预测
- 参数校验关键点：
  - `main._coerce_params()` 会按 `params_schema` 强制类型、枚举与对象结构校验并裁剪无关字段  
    - 位置：[main.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/main.py#L290-L334)

### 4.10 回测（backtest.py + main.py 入口）

回测入口 API：`POST /api/v1/backtest/run`  
实现位置：[main.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/main.py#L373-L453)

执行引擎：[backtest.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/backtest.py)

- `run_backtest(df, strategy_cls, strategy_params, initial_cash, commission, requires_weekly)`：
  - 内部按需 `import backtrader`，缺失则返回 `BacktestResult(metrics={"error":"backtrader_missing",...})`
  - `PandasDaily` feed 扩展了 `chan_signal/chan_zg/chan_zd` 三条线（用于部分策略）
  - 添加 analyzer：Sharpe、DrawDown、TradeAnalyzer、Returns
  - 返回：
    - `metrics`：收益、年化、最大回撤、夏普、交易次数、胜率等
    - `trades`：从策略 `_trade_log` 抽取的交易明细（pnl、pnlcomm、size、trade_date）

### 4.11 缠论字段注入（chan_engine.py）

当策略 `requires_chan=True` 时，回测前会注入缠论字段：

- 入口：`add_chan_fields(df, backend, symbol)` [chan_engine.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/chan_engine.py#L109-L153)
- 后端模式：
  - `chanpy`：导入 `chanpy_wrapper.run_chan`
  - `self`：导入 `chan_analyzer.ChanAnalyzer`
- 关键依赖：函数会向上搜索仓库内 `week5/课程代码-20260314/CASE-缠论精华量化` 并加入 `sys.path`  
  - 搜索逻辑：`_find_chan_case_dir()` [chan_engine.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/chan_engine.py#L21-L30)
- 输出列：
  - `chan_signal`：信号标记（例如第三类买卖点映射为 3/-3）
  - `chan_zg/chan_zd`：中枢上沿/下沿（按日期区间铺到每日）

---

## 5. 依赖关系

### 5.1 Python 依赖

- 基础依赖：[requirements.txt](file:///Users/apple/Desktop/ai_huahua/zoe/requirements.txt)
  - `fastapi` / `uvicorn` / `pydantic` / `python-dotenv` / `pymysql` / `pandas` / `numpy` / `Jinja2`
- 指标（可选）：[requirements-talib.txt](file:///Users/apple/Desktop/ai_huahua/zoe/requirements-talib.txt)
  - `ta-lib`
- 回测（可选）：[requirements-backtest.txt](file:///Users/apple/Desktop/ai_huahua/zoe/requirements-backtest.txt)
  - `backtrader`

### 5.2 外部系统依赖

- MySQL：提供 `trade_stock_daily`、`trade_stock_financial` 的数据
- （可选）缠论课程代码：当回测策略启用 `requires_chan` 时，需要仓库内存在 week5 对应 CASE 目录（见 4.11）

---

## 6. 关键类与函数速查

- 入口与路由：
  - `app = FastAPI(...)`：[main.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/main.py#L27-L32)
  - 回测 API：`api_backtest()`：[main.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/main.py#L383-L453)
- 配置：
  - `Settings` / `load_settings()`：[config.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/config.py#L9-L49)
- 数据读取：
  - `load_daily_ohlcv()`：[market_data.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/market_data.py#L28-L68)
  - `latest_financial_row()`：[market_data.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/market_data.py#L108-L134)
- 指标：
  - `add_technical_indicators()`：[indicators.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/indicators.py#L32-L55)
- 信号：
  - `generate_signals()`：[signals.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/signals.py#L120-L187)
- 选股：
  - `screen_financial()`：[screener.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/screener.py#L32-L72)
  - `score_factors()`：[screener.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/screener.py#L104-L147)
- 策略库：
  - `StrategyMeta`：[strategy_registry.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/strategy_registry.py#L7-L18)
  - `get_strategy_registry()`：[strategy_registry.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/strategy_registry.py#L1216-L1217)
- 回测：
  - `run_backtest()`：[backtest.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/backtest.py#L26-L134)
- 参数校验：
  - `_coerce_params()`：[main.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/main.py#L290-L334)

---

## 7. 常见问题定位（从代码角度）

- `/health` 显示 `db=false`：
  - 检查 `.env` 的 DB_HOST/PORT/USER/PASSWORD/NAME
  - DB 访问逻辑： [db.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/db.py)
- 指标计算异常或结果为 NaN：
  - 指标实现： [indicators.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/indicators.py)
  - fallback 实现： [_talib_fallback.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/_talib_fallback.py)
- 回测接口返回 backtrader_missing：
  - 入口处理： [main.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/main.py#L399-L409)
  - 安装：`pip install -r requirements-backtest.txt`
- 回测启用缠论失败（chan_case_dir_not_found / chan_engine_failed）：
  - 路径搜索： [chan_engine.py](file:///Users/apple/Desktop/ai_huahua/zoe/zoe/app/chan_engine.py#L21-L30)
  - 需要仓库存在 week5 对应 CASE 目录，且 Python 可导入其中模块

