## Zoe：数字员工分析师（策略计算 & 因子挖掘）

Zoe 是一个面向 AI 量化交易的“数字员工分析师”。她只负责计算与生成信号（指标、选股评分、回测结果），不负责资金管理与下单。

### 功能

- 技术指标：从 MySQL 读取日线（`huahua_trade.trade_stock_daily`），实时计算 MA / MACD / RSI / 布林带
- 生成信号：趋势突破 / 震荡下轨等规则信号，并输出评分（0-100）与原因
- 选股：财务阈值筛选、多因子打分 TopN
- 策略库：策略列表 + 参数预设管理
- 回测：Backtrader 回测与指标汇总（收益/回撤/胜率等）
- Web：自带独立 Web 控制台（无需 Node）

---

## 1. 环境要求

- Python 3.10+
- MySQL 8.0+（数据库：`huahua_trade`）

### TA-Lib 说明（Windows）

本项目优先使用 `TA-Lib` 计算指标。Windows 上安装 TA-Lib 可能需要预编译 wheel。

- 如果你已经在课程环境里成功安装过 `talib`，直接按下方步骤安装依赖即可。
- 若安装失败，可先跳过 `ta-lib`，Zoe 仍会使用内置的纯 Pandas 备选实现（指标结果可能与 TA-Lib 略有差异）。

---

## 2. 配置

复制配置模板并按需修改：

```bash
copy .env.example .env
```

默认数据库配置为：

- DB_NAME=huahua_trade
- DB_USER=root
- DB_PASSWORD=root

---

## 3. 安装依赖

建议使用虚拟环境：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

如需启用 TA-Lib（优先的指标实现）：

```bash
pip install -r requirements-talib.txt
```

如需启用 Backtrader 回测：

```bash
pip install -r requirements-backtest.txt
```

---

## 4. 启动

```bash
python -m zoe.app.main
```

启动后访问：

- Web 控制台：http://127.0.0.1:8010/
- 健康检查：http://127.0.0.1:8010/health

---

## 5. 常用 API

### 技术指标序列

```bash
curl "http://127.0.0.1:8010/api/v1/technical/series?stock_code=600519.SH&start=2024-01-01&end=2025-01-01"
```

### 信号 + 评分

```bash
curl "http://127.0.0.1:8010/api/v1/signals?stock_code=600519.SH&start=2024-01-01&end=2025-01-01"
```

---

## 6. 数据表

Zoe 默认使用以下表（来自课程 SQL）：

- `trade_stock_daily`：日线 OHLCV
- `trade_stock_financial`：季度财务数据（用于财务选股）
