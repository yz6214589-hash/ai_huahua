# 数据库表结构扩展说明文档

## 概述

本文档记录了腾讯云 MySQL 数据库 `huahua_trade` 的表结构扩展情况，用于支持新增和优化的功能模块：

- ✅ 信号中心
- ✅ 绩效报告生成
- ✅ 主力识别
- ✅ 风控看板
- ✅ 风控审批流程与节点
- ✅ 模拟盘功能
- ✅ 基本面选股优化

## 数据库连接信息

| 项目 | 值 |
|------|-----|
| 主机 | bj-cdb-6zjqetya.sql.tencentcdb.com |
| 端口 | 25341 |
| 数据库 | huahua_trade |
| 用户 | root |

## 当前数据库状态

- **总表数**: 60 张
- **新增表**: 22 张
- **扩展字段表**: 3 张

---

## 一、新增数据表

### 1. 信号中心模块

| 表名 | 说明 | 状态 |
|------|------|------|
| `trade_signal_rule` | 信号规则表 | ✅ 已存在 |
| `trade_signal_record` | 信号记录表 | ✅ 已存在 |
| `trade_signal_rule_condition` | 信号规则条件表 | ✅ 已存在 |
| `trade_signal_snapshot` | 信号快照表 | ✅ 已存在 |
| `trade_signal_statistic` | 信号统计表 | ✅ 已存在 |

**trade_signal_record 关键字段**:
- `signal_id`: 信号唯一标识
- `stock_code`: 股票代码
- `signal_type`: 信号类型（buy/sell/hold）
- `strength`: 信号强度(1-5)
- `score`: 综合评分
- `reason`: 信号生成原因
- `trade_date`: 交易日期

---

### 2. 模拟盘模块

| 表名 | 说明 | 状态 |
|------|------|------|
| `trade_sim_account` | 模拟账户表 | ✅ 已存在 |
| `trade_sim_position` | 模拟持仓表 | ✅ 已存在 |
| `trade_sim_trade` | 模拟交易记录表 | ✅ 已存在 |

**trade_sim_account 关键字段**:
- `account_id`: 账户ID
- `account_name`: 账户名称
- `initial_balance`: 初始资金
- `current_balance`: 当前余额
- `total_assets`: 总资产
- `pnl`: 盈亏金额

**trade_sim_trade 关键字段**:
- `trade_no`: 交易编号
- `stock_code`: 股票代码
- `side`: 交易方向(buy/sell)
- `price`: 成交价格
- `volume`: 成交数量
- `amount`: 成交金额
- `commission`: 手续费

---

### 3. 主力识别模块

| 表名 | 说明 | 状态 |
|------|------|------|
| `trade_mainforce_activity` | 主力活动表 | ✅ 已存在 |
| `trade_mainforce_flow` | 主力资金流表 | ✅ 已存在 |
| `trade_mainforce_position_change` | 主力持仓变动表 | ✅ 已存在 |
| `trade_mainforce_statistic` | 主力统计表 | ✅ 已存在 |
| `trade_mainforce_alert_rule` | 主力预警规则表 | ✅ 已存在 |
| `trade_kline_marker` | K线标记表 | ✅ 已存在 |

**trade_mainforce_activity 关键字段**:
- `activity_id`: 活动ID
- `stock_code`: 股票代码
- `activity_type`: 活动类型(buy_in/sell_out/accumulate/distribute)
- `mainforce_type`: 主力类型(机构/游资/北向资金)
- `net_amount`: 净额
- `indicators`: 指标数据(JSON)
- `alert_status`: 预警状态

---

### 4. 审批流程模块

| 表名 | 说明 | 状态 |
|------|------|------|
| `trade_approval_template` | 审批模板表 | ✅ 已存在 |
| `trade_approval_instance` | 审批实例表 | ✅ 已存在 |
| `trade_approval_node_instance` | 审批节点实例表 | ✅ 已存在 |
| `trade_approval_record` | 审批记录表 | ✅ 已存在 |

**trade_approval_template 关键字段**:
- `template_id`: 模板ID
- `template_name`: 模板名称
- `nodes`: 节点配置(JSON)
- `applicable_scene`: 适用场景

**trade_approval_instance 关键字段**:
- `instance_id`: 实例ID
- `template_id`: 关联模板ID
- `status`: 状态(pending/approved/rejected)
- `current_node`: 当前节点
- `applicant_id`: 申请人ID

---

### 5. 风控模块

| 表名 | 说明 | 状态 |
|------|------|------|
| `trade_risk_rule` | 风控规则表 | ✅ 已存在 |
| `trade_risk_event` | 风险事件表 | ✅ 已存在 |
| `trade_risk_alert` | 风险预警表 | ✅ 已存在 |
| `trade_risk_operation_log` | 风控操作日志表 | ✅ 已存在 |
| `trade_position_risk` | 持仓风险表 | ✅ 已存在 |
| `trade_account_risk_metric` | 账户风险指标表 | ✅ 已存在 |

**trade_risk_event 关键字段**:
- `event_id`: 事件ID
- `event_type`: 事件类型(stop_loss/position_overflow/liquidity)
- `risk_level`: 风险等级(low/medium/high/critical)
- `stock_code`: 关联股票
- `account_id`: 关联账户
- `status`: 处理状态(pending/confirmed/processed/ignored)
- `triggered_rule_id`: 触发规则ID

---

### 6. 绩效报告模块

| 表名 | 说明 | 状态 |
|------|------|------|
| `trade_performance_report` | 绩效报告表 | ✅ 已存在 |
| `trade_backtest_record` | 回测记录表 | ✅ 已存在 |

**trade_performance_report 关键字段**:
- `report_id`: 报告ID
- `report_type`: 报告类型(common/plus)
- `account_id`: 关联账户ID
- `strategy_name`: 策略名称
- `start_date` / `end_date`: 时间范围
- `total_return`: 总收益率(%)
- `annualized_return`: 年化收益率(%)
- `max_drawdown`: 最大回撤(%)
- `sharpe_ratio`: 夏普比率
- `win_rate`: 胜率(%)
- `chart_data`: 图表数据(JSON)

---

## 二、扩展字段表

### trade_stock_financial（财务数据表）

**新增字段**:

| 字段名 | 类型 | 说明 | 状态 |
|--------|------|------|------|
| `operating_margin` | DECIMAL(10,4) | 营业利润率(%) | ✅ 已存在 |
| `quick_ratio` | DECIMAL(10,4) | 速动比率 | ✅ 已存在 |
| `total_asset_turnover` | DECIMAL(10,4) | 总资产周转率 | ✅ 已存在 |
| `free_cash_flow` | DECIMAL(20,4) | 自由现金流(亿) | ✅ 已存在 |
| `dividend_yield` | DECIMAL(10,4) | 股息率(%) | ✅ 已存在 |
| `ebitda` | DECIMAL(20,4) | EBITDA(亿) | ✅ 已存在 |
| `ev_ebitda` | DECIMAL(10,4) | EV/EBITDA | ✅ 已存在 |

**原有字段保留**:
- pe_ttm, pb, roe, gross_margin, net_margin
- revenue_growth_yoy, profit_growth_yoy
- debt_ratio, revenue, net_profit, eps
- market_cap

---

## 三、后端API适配情况

| 模块 | 文件路径 | 适配状态 | 存储类型变更 |
|------|----------|----------|--------------|
| 信号中心 | `backend/api/signals.py` | ✅ 已适配 | 内存 → MySQL |
| 模拟账户 | `backend/api/sim_account.py` | ✅ 已适配 | 内存 → MySQL |
| 主力识别 | `backend/api/mainforce.py` | ✅ 已适配 | SQLite → MySQL |
| 审批流程 | `backend/api/approval.py` | ✅ 已适配 | 内存 → MySQL |
| 风控看板 | `backend/api/risk_kris.py` | ✅ 已适配 | SQLite → MySQL |
| 绩效报告 | `backend/api/performance.py` | ✅ 已适配 | MySQL |
| 基本面选股 | `backend/api/stock_select.py` | ✅ 已适配 | 扩展字段支持 |

---

## 四、数据迁移说明

### 迁移策略
1. **新增表**: 使用 `CREATE TABLE IF NOT EXISTS` 语法，确保幂等性
2. **扩展字段**: 使用 `ALTER TABLE ADD COLUMN`，通过 Python 脚本检查字段存在性后添加
3. **数据安全**: 使用事务处理，迁移失败自动回滚

### 迁移脚本
- 统一迁移脚本: `backend/migrations/010_unified_migration.sql`
- 字段扩展脚本: `run_alter_columns.py`

---

## 五、验证结果

### 数据库连接验证
```
数据库: huahua_trade
状态: ✅ 连接成功
表总数: 60 张
```

### 新增表验证
| 功能模块 | 表数 | 状态 |
|----------|------|------|
| 信号中心 | 5 张 | ✅ 全部存在 |
| 模拟盘 | 3 张 | ✅ 全部存在 |
| 主力识别 | 6 张 | ✅ 全部存在 |
| 审批流程 | 4 张 | ✅ 全部存在 |
| 风控模块 | 6 张 | ✅ 全部存在 |
| 绩效报告 | 2 张 | ✅ 全部存在 |

### 扩展字段验证
```
trade_stock_financial 扩展字段:
  - operating_margin: ✅ 已存在
  - quick_ratio: ✅ 已存在
  - total_asset_turnover: ✅ 已存在
  - free_cash_flow: ✅ 已存在
  - dividend_yield: ✅ 已存在
  - ebitda: ✅ 已存在
  - ev_ebitda: ✅ 已存在
```

---

## 六、后端服务状态

```
服务地址: http://localhost:8000
状态: ✅ 运行正常
注册路由: 18 个
任务调度器: ✅ 启动成功
```

---

## 七、注意事项

1. **数据兼容性**: 所有原有数据表和字段保持不变，确保历史数据不丢失
2. **索引优化**: 新增表均已创建必要索引，优化查询性能
3. **事务保障**: 所有数据库操作均使用事务，确保数据一致性
4. **JSON字段**: 复杂数据结构使用 JSON 类型存储，便于灵活扩展

---

**生成时间**: 2026-05-16  
**数据库版本**: MySQL (腾讯云CDB)  
**文档版本**: v1.0
