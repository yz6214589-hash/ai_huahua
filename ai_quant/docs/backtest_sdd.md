# 回测系统优化 - 软件设计文档 (SDD)

## 一、系统架构

### 1.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                         前端 (React + ECharts)                   │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│ 回测配置面板  │  图表展示区   │  历史管理页   │  参数优化页        │
│ (区间/成本/   │ (净值/回撤/  │ (列表/对比/   │ (网格搜索/         │
│  基准/参数)   │  热力图)     │  导出)       │  敏感度)           │
└──────┬───────┴──────┬───────┴──────┬───────┴─────────┬──────────┘
       │              │              │                 │
       ▼              ▼              ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    API 层 (FastAPI Router)                        │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│ /backtest/   │ /backtest/   │ /backtest/   │ /backtest/         │
│  run         │  walk-forward│  history     │  param-search      │
└──────┬───────┴──────┬───────┴──────┬───────┴─────────┬──────────┘
       │              │              │                 │
       ▼              ▼              ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                   核心引擎层 (backend/core/strategy/)             │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│backtest_     │walk_forward_ │metrics_      │param_optimizer.py  │
│engine.py     │engine.py     │calculator.py │                    │
│(Backtrader   │(滚动验证)    │(指标计算)    │(参数搜索)          │
│ 回测执行)    │              │              │                    │
├──────────────┼──────────────┼──────────────┤                    │
│benchmark_    │backtest_     │strategy_     │                    │
│loader.py     │storage.py    │registry.py   │                    │
│(基准数据)    │(历史持久化)  │(策略注册)    │                    │
└──────────────┴──────────────┴──────────────┴────────────────────┘
       │              │              │
       ▼              ▼              ▼
┌──────────────────────────────────────────────────────────────────┐
│                   数据层 (MySQL + 文件系统)                       │
├──────────────┬──────────────┬──────────────────────────────────┤
│trade_stock_  │backtest_     │.ai_quant/                        │
│daily         │records       │(实例/配置JSON)                    │
│(行情数据)    │(回测历史)    │                                   │
└──────────────┴──────────────┴──────────────────────────────────┘
```

### 1.2 模块依赖关系

```
analysis_zoe.py (API路由)
    ├── backtest_engine.py (核心回测)
    │       └── backtrader (第三方库)
    ├── metrics_calculator.py (指标计算)
    │       └── numpy, scipy
    ├── benchmark_loader.py (基准数据)
    │       └── core.db (数据库)
    ├── walk_forward_engine.py (滚动验证)
    │       └── backtest_engine.py
    ├── param_optimizer.py (参数优化)
    │       └── backtest_engine.py
    ├── backtest_storage.py (历史持久化)
    │       └── core.db (数据库)
    ├── strategy_registry.py (策略注册)
    └── multi_agent_backtest.py (批量回测)
            └── backtest_engine.py
```

---

## 二、模块划分

### 2.1 后端新增模块

| 模块 | 文件路径 | 职责 |
|------|---------|------|
| 指标计算器 | `core/strategy/metrics_calculator.py` | 计算Alpha/Beta/IR/Calmar/Sortino/波动率等 |
| 基准加载器 | `core/strategy/benchmark_loader.py` | 从DB加载基准指数数据 |
| 滚动验证引擎 | `core/strategy/walk_forward_engine.py` | Walk Forward Analysis |
| 回测存储 | `core/strategy/backtest_storage.py` | 回测结果CRUD |
| 参数优化器 | `core/strategy/param_optimizer.py` | 网格搜索与敏感性分析 |

### 2.2 后端修改模块

| 模块 | 文件路径 | 改动说明 |
|------|---------|---------|
| 回测引擎 | `core/strategy/backtest_engine.py` | 增加滑点、买卖分费率、区间运行、基准数据输入 |
| API路由 | `api/analysis_zoe.py` | 新增区间回测/滚动验证/历史管理/参数搜索API |

### 2.3 前端新增组件

| 组件 | 文件路径 | 职责 |
|------|---------|------|
| 回测图表 | `components/BacktestCharts.tsx` | 净值曲线、回撤曲线、月度热力图、盈亏分布 |
| 滚动验证面板 | `components/WalkForwardPanel.tsx` | 滚动验证配置与结果展示 |
| 回测历史页 | `pages/BacktestHistory.tsx` | 回测历史列表与对比 |
| 参数优化页 | `pages/ParamOptimizer.tsx` | 参数网格搜索 |

### 2.4 前端修改组件

| 组件 | 文件路径 | 改动说明 |
|------|---------|---------|
| 回测页面 | `pages/StrategyBacktest.tsx` | 增加区间配置、交易成本、基准选择、图表区 |

---

## 三、接口设计

### 3.1 单股回测 - 增强版

**POST** `/api/v1/analysis/backtest/run`

请求体（在现有基础上扩展，新增字段均为可选）：

```python
class BacktestReq(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 100000.0
    # === 新增字段 ===
    # 交易成本
    commission_buy: float = 0.0003        # 买入佣金率
    commission_sell: float = 0.0013       # 卖出佣金率（含印花税）
    slippage_pct: float = 0.0             # 滑点百分比
    slippage_fixed: float = 0.0           # 固定滑点（元）
    min_commission: float = 5.0           # 最低手续费
    # 基准
    benchmark_code: str = "000300.SH"     # 基准指数代码
    # 区间
    interval_mode: str = "full"           # full / train_val_test
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    custom_intervals: dict | None = None  # 自定义区间
```

响应体（扩展metrics）：

```python
{
    "metrics": {
        # 现有字段
        "initial_nav": 100000.0,
        "final_nav": 125000.0,
        "total_return": 25.0,
        "annual_return": 12.5,
        "sharpe": 1.23,
        "max_drawdown": 8.5,
        "num_trades": 45,
        "won": 28,
        "lost": 17,
        "win_rate": 62.2,
        # === 新增字段 ===
        "volatility": 15.3,               # 年化波动率(%)
        "downside_volatility": 10.2,       # 下行波动率(%)
        "sortino": 1.85,                   # Sortino比率
        "calmar": 1.47,                    # Calmar比率
        "max_dd_duration": 35,             # 最大回撤持续天数
        "profit_factor": 2.15,             # 盈亏比
        "avg_trade_pnl": 555.6,            # 平均每笔盈亏
        "max_consecutive_wins": 5,         # 最大连续盈利次数
        "max_consecutive_losses": 3,        # 最大连续亏损次数
        # 基准对比
        "benchmark_return": 15.2,           # 基准收益率(%)
        "excess_return": 9.8,              # 超额收益(%)
        "alpha": 8.5,                      # Alpha(%)
        "beta": 0.85,                      # Beta系数
        "tracking_error": 6.2,             # 跟踪误差(%)
        "information_ratio": 1.37,         # 信息比率
    },
    "benchmark_nav_log": [                 # 基准净值序列
        {"date": "2023-01-03", "nav": 100000},
        {"date": "2023-01-04", "nav": 100500},
    ],
    "drawdown_log": [                       # 回撤序列
        {"date": "2023-01-03", "drawdown": 0.0},
        {"date": "2023-01-04", "drawdown": -0.02},
    ],
    "monthly_returns": [                    # 月度收益
        {"month": "2023-01", "return": 2.5},
        {"month": "2023-02", "return": -1.2},
    ],
    "interval_results": [                   # 区间结果（interval_mode非full时）
        {
            "interval": "train",
            "start_date": "2023-01-01",
            "end_date": "2024-08-31",
            "metrics": { ... }
        },
        {
            "interval": "val",
            "start_date": "2024-09-01",
            "end_date": "2025-02-28",
            "metrics": { ... }
        },
        {
            "interval": "test",
            "start_date": "2025-03-01",
            "end_date": "2025-12-31",
            "metrics": { ... }
        }
    ],
    "trades": [ ... ],
    "nav_log": [ ... ],
    "strategy_id": "ma_dual",
    "stock_code": "600519.SH",
    "start_date": "2023-01-01",
    "end_date": "2025-12-31",
    "backtest_id": "bt_abc123"
}
```

### 3.2 滚动验证

**POST** `/api/v1/analysis/backtest/walk-forward`

```python
class WalkForwardReq(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 100000.0
    # 滚动配置
    mode: str = "fixed"              # fixed（固定窗口）/ expanding（展开窗口）
    train_window_years: int = 5      # 训练窗口年数
    test_window_years: int = 1       # 测试窗口年数
    step_years: int = 1              # 步长年数
    # 交易成本
    commission_buy: float = 0.0003
    commission_sell: float = 0.0013
    slippage_pct: float = 0.0
    benchmark_code: str = "000300.SH"
```

响应：

```python
{
    "total_windows": 3,
    "windows": [
        {
            "window_id": 1,
            "train_start": "2018-01-01",
            "train_end": "2022-12-31",
            "test_start": "2023-01-01",
            "test_end": "2023-12-31",
            "train_metrics": { ... },
            "test_metrics": { ... }
        },
        # ...
    ],
    "stability": {
        "avg_test_return": 12.5,
        "std_test_return": 3.2,
        "min_test_return": 8.1,
        "max_test_return": 16.3,
        "consistency_ratio": 1.0,         # 正收益期数/总期数
    },
    "aggregated_metrics": { ... }
}
```

### 3.3 回测历史

**GET** `/api/v1/analysis/backtest/records`

查询参数：`strategy_id`, `stock_code`, `page`, `page_size`

**GET** `/api/v1/analysis/backtest/records/{backtest_id}`

**DELETE** `/api/v1/analysis/backtest/records/{backtest_id}`

**POST** `/api/v1/analysis/backtest/compare`

请求体：`{ "backtest_ids": ["bt_abc123", "bt_def456"] }`

### 3.4 参数搜索

**POST** `/api/v1/analysis/backtest/param-search`

```python
class ParamSearchReq(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str
    param_grid: dict[str, list[Any]]     # 如 {"fast_period": [5,10,15], "slow_period": [20,30,40]}
    initial_cash: float = 100000.0
    benchmark_code: str = "000300.SH"
```

响应：

```python
{
    "total_combinations": 9,
    "results": [
        {
            "params": {"fast_period": 5, "slow_period": 20},
            "metrics": {"total_return": 15.2, "sharpe": 1.1, ...},
        },
        # ...
    ],
    "best_by_return": { "params": {...}, "metrics": {...} },
    "best_by_sharpe": { "params": {...}, "metrics": {...} },
}
```

---

## 四、数据结构

### 4.1 数据库表

```sql
CREATE TABLE backtest_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    backtest_id VARCHAR(64) UNIQUE NOT NULL,
    strategy_id VARCHAR(64) NOT NULL,
    strategy_name VARCHAR(128),
    stock_code VARCHAR(32) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_cash DECIMAL(18,2) DEFAULT 100000.00,
    params JSON,
    cost_config JSON,
    benchmark_code VARCHAR(32) DEFAULT '000300.SH',
    interval_mode VARCHAR(32) DEFAULT 'full',
    metrics JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_strategy (strategy_id),
    INDEX idx_stock (stock_code),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE backtest_nav_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    backtest_id VARCHAR(64) NOT NULL,
    trade_date DATE NOT NULL,
    nav DECIMAL(18,4),
    benchmark_nav DECIMAL(18,4),
    drawdown DECIMAL(10,6),
    INDEX idx_backtest (backtest_id),
    INDEX idx_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 4.2 核心数据类

```python
@dataclass
class EnhancedBacktestResult:
    # 基础回测结果
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    nav_log: list[dict[str, Any]]
    # 新增
    benchmark_nav_log: list[dict[str, Any]]
    drawdown_log: list[dict[str, Any]]
    monthly_returns: list[dict[str, Any]]
    interval_results: list[dict[str, Any]]
    backtest_id: str
```

---

## 五、算法设计

### 5.1 区间划分算法

```python
def split_intervals(
    start: str, end: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> dict[str, tuple[str, str]]:
    """按比例划分训练/验证/测试区间"""
    total_days = (pd.Timestamp(end) - pd.Timestamp(start)).days
    train_end = pd.Timestamp(start) + pd.Timedelta(days=int(total_days * train_ratio))
    val_end = train_end + pd.Timedelta(days=int(total_days * val_ratio))
    return {
        "train": (start, train_end.strftime("%Y-%m-%d")),
        "val": (train_end.strftime("%Y-%m-%d"), val_end.strftime("%Y-%m-%d")),
        "test": (val_end.strftime("%Y-%m-%d"), end),
    }
```

### 5.2 Alpha/Beta计算（CAPM模型）

```python
def calc_alpha_beta(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.03,
) -> tuple[float, float]:
    """使用线性回归计算Alpha和Beta"""
    rf_daily = risk_free_rate / 252
    excess_strategy = strategy_returns - rf_daily
    excess_benchmark = benchmark_returns - rf_daily
    beta = excess_strategy.cov(excess_benchmark) / excess_benchmark.var()
    alpha = (excess_strategy.mean() - beta * excess_benchmark.mean()) * 252
    return float(alpha), float(beta)
```

### 5.3 信息比率（IR）

```python
def calc_information_ratio(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """IR = 超额收益均值 / 跟踪误差"""
    excess = strategy_returns - benchmark_returns
    tracking_error = excess.std() * (252 ** 0.5)
    if tracking_error == 0:
        return 0.0
    annualized_excess = excess.mean() * 252
    return float(annualized_excess / tracking_error)
```

### 5.4 滚动验证引擎

```python
def generate_walk_forward_windows(
    start: str, end: str,
    train_years: int = 5,
    test_years: int = 1,
    step_years: int = 1,
    mode: str = "fixed",
) -> list[dict[str, str]]:
    """生成滚动窗口"""
    windows = []
    current_train_start = pd.Timestamp(start)
    while True:
        train_end = current_train_start + pd.DateOffset(years=train_years)
        test_end = train_end + pd.DateOffset(years=test_years)
        if test_end > pd.Timestamp(end):
            break
        windows.append({
            "train_start": current_train_start.strftime("%Y-%m-%d"),
            "train_end": train_end.strftime("%Y-%m-%d"),
            "test_start": train_end.strftime("%Y-%m-%d"),
            "test_end": test_end.strftime("%Y-%m-%d"),
        })
        if mode == "fixed":
            current_train_start += pd.DateOffset(years=step_years)
        else:  # expanding
            train_end += pd.DateOffset(years=step_years)
            current_train_start = pd.Timestamp(start)
            # expanding模式下训练起点不变，终点扩展
    return windows
```

### 5.5 参数网格搜索

```python
def grid_search(
    param_grid: dict[str, list[Any]],
) -> list[dict[str, Any]]:
    """生成参数组合的笛卡尔积"""
    import itertools
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = []
    for combo in itertools.product(*values):
        combos.append(dict(zip(keys, combo)))
    return combos
```

---

## 六、安全设计

1. **输入校验**：所有日期参数校验格式和合理性（start <= end）
2. **参数范围限制**：grid_search最多1000种组合，防止资源耗尽
3. **SQL注入防护**：使用参数化查询（现有core.db已实现）
4. **数据隔离**：backtest_id使用UUID，防止越权访问
5. **并发控制**：滚动验证和参数搜索使用线程池，max_workers限制为4
6. **中文编码**：所有API响应设置charset=utf-8，数据库使用utf8mb4
