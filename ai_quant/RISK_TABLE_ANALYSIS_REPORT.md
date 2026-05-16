# 风控功能数据库表结构分析报告

## 一、数据库连接信息

### 连接配置
- **主机**: bj-cdb-6zjqetya.sql.tencentcdb.com:25341
- **数据库**: huahua_trade
- **用户名**: root
- **表数量**: 34 个

### 数据库类型
腾讯云数据库 (CDB)

---

## 二、现有风控相关表分析

### 2.1 已存在的风控表

#### 1. **trade_risk_rule** - 风控规则表 ✅

**表结构**:
```sql
- id: bigint(20) PRIMARY KEY AUTO_INCREMENT
- rule_code: varchar(64) UNIQUE
- rule_name: varchar(100)
- rule_type: varchar(20)
- decision: varchar(20)
- condition_expr: text
- condition_desc: varchar(255)
- max_position_pct: decimal(8,2)  -- 最大持仓比例
- max_single_loss_pct: decimal(8,2)  -- 最大单笔亏损比例
- max_daily_loss_pct: decimal(8,2)  -- 最大日亏损比例
- max_concentration_pct: decimal(8,2)  -- 最大集中度
- min_cash_reserve_pct: decimal(8,2)  -- 最小现金储备
- circuit_breaker_pct: decimal(8,2)  -- 熔断比例
- priority: int(11)
- enabled: tinyint(1)
- account_id: varchar(32)
- notes: text
- created_at: datetime
- updated_at: datetime
```

**数据行数**: 0

**优点**:
- ✅ 已包含基本的风控规则字段
- ✅ 支持多种风控条件
- ✅ 有优先级设置

**问题**:
- ❌ 缺少触发统计字段
- ❌ 缺少最后触发时间
- ❌ 缺少触发后的动作记录

---

#### 2. **trade_live_capital** - 实时资金表

**关键字段**:
- account_id, total_capital, available_capital, frozen_capital
- market_value, total_asset
- leverage_ratio, margin_ratio
- risk_score, risk_level

**数据行数**: 0

**优点**:
- ✅ 已包含账户级别的风险指标
- ✅ 有杠杆率和保证金比例
- ✅ 有风险评分和等级

---

#### 3. **trade_live_position** - 实时持仓表

**关键字段**:
- account_id, stock_code, stock_name
- quantity, available_quantity, frozen_quantity
- avg_cost, current_price, market_value
- profit_loss, profit_loss_pct
- today_profit_loss, today_profit_loss_pct
- position_ratio
- stop_loss_price, target_price

**数据行数**: 0

**优点**:
- ✅ 已包含持仓信息
- ✅ 有盈亏计算
- ✅ 有止损价设置
- ❌ 缺少风险值字段（risk_value）

---

#### 4. **trade_live_signal** - 实时信号表

**关键字段**:
- signal_id, account_id, source, stock_code
- direction, signal_type, strength, confidence
- target_price, stop_loss_price
- position_size_pct
- status (pending, approved, rejected, executed)
- approved_by, approved_at
- expires_at

**数据行数**: 0

**优点**:
- ✅ 已包含信号管理
- ✅ 有审批流程
- ✅ 有执行跟踪

---

#### 5. **trade_live_event** - 实时事件表

**关键字段**:
- event_id, account_id
- event_type, event_level
- message, detail
- related_id
- created_at

**数据行数**: 0

---

### 2.2 其他相关表

#### 1. **trade_system_event** - 系统事件表

**关键字段**:
- event_id, event_level, event_module, event_type
- message, detail
- user_id, ip_address
- duration_ms
- created_at

**数据行数**: 0

---

## 三、风控看板需求对比

### 3.1 需要的数据

| 功能模块 | 需要的数据 | 现有表 | 是否满足 |
|---------|----------|--------|--------|
| 风险概览 | 总体风险评分 | trade_live_capital.risk_score | ✅ 满足 |
| 风险概览 | 风险等级分布 | trade_live_capital.risk_level | ✅ 满足 |
| 风险概览 | 今日新增风险事件 | trade_live_event | ⚠️ 需要扩展 |
| 风险概览 | 待处理风险告警 | trade_live_signal | ⚠️ 需要筛选 |
| 持仓风险 | 各持仓股票风险值 | trade_live_position | ❌ 缺少risk_value |
| 持仓风险 | 各持仓股票风险等级 | trade_live_position | ❌ 缺少risk_level |
| 杠杆率 | 当前杠杆使用情况 | trade_live_capital.leverage_ratio | ✅ 满足 |
| 仓位分布 | 持仓占比分布 | trade_live_position.position_ratio | ✅ 满足 |
| 流动性 | 资金流动性指标 | trade_live_capital | ⚠️ 需要计算 |
| 实时告警 | 告警列表 | trade_live_signal | ⚠️ 需要筛选 |
| 历史事件 | 事件查询列表 | trade_live_event | ⚠️ 需要扩展 |
| 风控规则 | 规则状态 | trade_risk_rule | ✅ 满足 |

---

## 四、优化建议

### 4.1 需要新建的表

#### 1. **risk_alerts** - 风控告警表

**建议结构**:
```sql
CREATE TABLE risk_alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    alert_code VARCHAR(64) UNIQUE,
    alert_type ENUM('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity', 'system'),
    level ENUM('red', 'orange', 'yellow', 'green'),
    stock_code VARCHAR(20),
    stock_name VARCHAR(100),
    account_id VARCHAR(32),
    message TEXT NOT NULL,
    metric_value DECIMAL(20, 4),
    threshold_value DECIMAL(20, 4),
    status ENUM('pending', 'confirmed', 'ignored', 'processed') DEFAULT 'pending',
    handler_id VARCHAR(64),
    handle_result TEXT,
    handled_at DATETIME,
    is_read TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_alert_type (alert_type),
    INDEX idx_level (level),
    INDEX idx_status (status),
    INDEX idx_account_id (account_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控告警表';
```

**理由**:
- 现有表无法区分不同级别的告警
- 需要独立的告警管理流程
- 需要告警的确认、处理、忽略操作

---

#### 2. **risk_events** - 风险事件表

**建议结构**:
```sql
CREATE TABLE risk_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_code VARCHAR(64) UNIQUE,
    event_type ENUM('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity'),
    risk_level ENUM('low', 'medium', 'high', 'critical'),
    stock_code VARCHAR(20),
    stock_name VARCHAR(100),
    position_id BIGINT,
    account_id VARCHAR(32) NOT NULL,
    description TEXT,
    event_data JSON,
    triggered_rule_id BIGINT,
    status ENUM('pending', 'confirmed', 'ignored', 'processed', 'expired') DEFAULT 'pending',
    handler_id VARCHAR(64),
    handle_comment TEXT,
    handled_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_event_type (event_type),
    INDEX idx_risk_level (risk_level),
    INDEX idx_status (status),
    INDEX idx_account_id (account_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (triggered_rule_id) REFERENCES trade_risk_rule(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风险事件表';
```

**理由**:
- 需要记录所有风险事件
- 需要事件的生命周期管理
- 需要与规则关联

---

#### 3. **risk_operation_logs** - 风控操作日志表

**建议结构**:
```sql
CREATE TABLE risk_operation_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    operator_id VARCHAR(64) NOT NULL,
    operator_name VARCHAR(100),
    operation_type ENUM('create_rule', 'update_rule', 'delete_rule', 'handle_alert', 'confirm_alert', 'ignore_alert', 'process_alert'),
    target_type ENUM('rule', 'alert', 'event', 'account'),
    target_id VARCHAR(64) NOT NULL,
    target_name VARCHAR(255),
    old_value JSON,
    new_value JSON,
    ip_address VARCHAR(50),
    user_agent VARCHAR(500),
    result ENUM('success', 'failed') NOT NULL,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_operator_id (operator_id),
    INDEX idx_operation_type (operation_type),
    INDEX idx_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控操作日志表';
```

**理由**:
- 需要审计所有风控操作
- 满足合规性要求
- 记录操作前后的值

---

### 4.2 需要扩展的表

#### 1. **扩展 trade_live_position**

```sql
ALTER TABLE trade_live_position
ADD COLUMN risk_value DECIMAL(10, 2) DEFAULT 0 COMMENT '风险值(0-100)',
ADD COLUMN risk_level ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low' COMMENT '风险等级',
ADD COLUMN var_95 DECIMAL(20, 4) COMMENT 'VaR 95%置信度',
ADD COLUMN volatility DECIMAL(10, 4) COMMENT '波动率',
ADD COLUMN beta DECIMAL(10, 4) COMMENT 'Beta值',
ADD INDEX idx_risk_level (risk_level),
ADD INDEX idx_risk_value (risk_value);
```

**理由**:
- 持仓风险是核心数据
- 需要计算VaR、波动率等风险指标
- 需要风险等级评估

---

#### 2. **扩展 trade_risk_rule**

```sql
ALTER TABLE trade_risk_rule
ADD COLUMN trigger_count INT DEFAULT 0 COMMENT '累计触发次数',
ADD COLUMN last_trigger_time DATETIME COMMENT '最后触发时间',
ADD COLUMN last_trigger_value VARCHAR(100) COMMENT '最后触发时的值',
ADD COLUMN action ENUM('alert', 'block', 'auto_close') DEFAULT 'alert' COMMENT '触发动作',
ADD COLUMN alert_template TEXT COMMENT '告警消息模板';
```

**理由**:
- 现有表缺少触发统计
- 需要记录触发动作
- 需要告警模板

---

### 4.3 不需要新建的表

1. ~~risk_rules~~ - 使用现有的 `trade_risk_rule`
2. ~~position_risks~~ - 扩展现有的 `trade_live_position`
3. ~~account_risk_metrics~~ - 使用现有的 `trade_live_capital`

---

## 五、实施计划

### 5.1 第一阶段（核心功能）

1. **新建 3 个表**
   - risk_alerts (风控告警表)
   - risk_events (风险事件表)
   - risk_operation_logs (操作日志表)

2. **扩展 2 个现有表**
   - trade_live_position (添加风险字段)
   - trade_risk_rule (添加触发统计)

### 5.2 第二阶段（完善功能）

1. 完善字段和索引
2. 插入示例数据
3. 测试验证

---

## 六、SQL 脚本

### 6.1 新建表 SQL

```sql
-- 风险告警表
CREATE TABLE risk_alerts (...);

-- 风险事件表
CREATE TABLE risk_events (...);

-- 操作日志表
CREATE TABLE risk_operation_logs (...);
```

### 6.2 扩展现有表 SQL

```sql
-- 扩展持仓表
ALTER TABLE trade_live_position ADD COLUMN ...;

-- 扩展规则表
ALTER TABLE trade_risk_rule ADD COLUMN ...;
```

---

## 七、总结

### 7.1 最终方案

- **新建表**: 3 个
- **扩展表**: 2 个
- **不需要新建**: 3 个

### 7.2 优势

1. **复用现有表**: 减少数据冗余
2. **最小改动**: 尽量扩展而非新建
3. **高兼容性**: 不影响现有功能
4. **可追溯**: 完整的操作日志

### 7.3 注意事项

1. 实施前做好数据备份
2. 按优先级分阶段实施
3. 充分测试后再上线
4. 保留回滚方案
