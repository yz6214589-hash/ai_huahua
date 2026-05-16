-- 风控管理系统数据库表结构（SQLite版本）
-- 版本: 1.0.0
-- 说明: 此文件用于在没有MySQL的情况下演示表结构

-- ============================================
-- 1. 风控规则表
-- ============================================
CREATE TABLE IF NOT EXISTS risk_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    rule_type TEXT NOT NULL CHECK(rule_type IN ('stop_loss', 'position_limit', 'liquidity', 'leverage', 'concentration')),
    condition TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'alert' CHECK(action IN ('alert', 'block', 'auto_close')),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'triggered')),
    priority INTEGER NOT NULL DEFAULT 0,
    trigger_count INTEGER NOT NULL DEFAULT 0,
    last_trigger_time DATETIME,
    last_trigger_value TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_risk_rules_type ON risk_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_risk_rules_status ON risk_rules(status);
CREATE INDEX IF NOT EXISTS idx_risk_rules_created_at ON risk_rules(created_at);

-- ============================================
-- 2. 风险事件表
-- ============================================
CREATE TABLE IF NOT EXISTS risk_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL CHECK(event_type IN ('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity', 'price_alert', 'volatility')),
    risk_level TEXT NOT NULL CHECK(risk_level IN ('low', 'medium', 'high', 'critical')),
    stock_code TEXT,
    stock_name TEXT,
    position_id TEXT,
    account_id TEXT NOT NULL,
    description TEXT,
    event_data TEXT,
    triggered_rule_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'ignored', 'processed', 'expired')),
    handler_id TEXT,
    handle_comment TEXT,
    handled_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (triggered_rule_id) REFERENCES risk_rules(id)
);

CREATE INDEX IF NOT EXISTS idx_risk_events_type ON risk_events(event_type);
CREATE INDEX IF NOT EXISTS idx_risk_events_level ON risk_events(risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_events_status ON risk_events(status);
CREATE INDEX IF NOT EXISTS idx_risk_events_stock ON risk_events(stock_code);
CREATE INDEX IF NOT EXISTS idx_risk_events_account ON risk_events(account_id);
CREATE INDEX IF NOT EXISTS idx_risk_events_created_at ON risk_events(created_at);
CREATE INDEX IF NOT EXISTS idx_risk_events_rule ON risk_events(triggered_rule_id);

-- ============================================
-- 3. 风控告警表
-- ============================================
CREATE TABLE IF NOT EXISTS risk_alerts (
    id TEXT PRIMARY KEY,
    alert_type TEXT NOT NULL CHECK(alert_type IN ('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity', 'price_alert', 'volatility', 'system')),
    level TEXT NOT NULL CHECK(level IN ('red', 'orange', 'yellow', 'green')),
    stock_code TEXT,
    stock_name TEXT,
    account_id TEXT NOT NULL,
    message TEXT NOT NULL,
    metric_value REAL,
    threshold_value REAL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'ignored', 'processed')),
    handler_id TEXT,
    handle_result TEXT,
    handled_at DATETIME,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_alerts_type ON risk_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_level ON risk_alerts(level);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_status ON risk_alerts(status);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_stock ON risk_alerts(stock_code);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_account ON risk_alerts(account_id);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_created_at ON risk_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_read ON risk_alerts(is_read);

-- ============================================
-- 4. 持仓风险表
-- ============================================
CREATE TABLE IF NOT EXISTS position_risks (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    position_value REAL NOT NULL,
    position_ratio REAL NOT NULL,
    risk_value REAL NOT NULL,
    risk_level TEXT NOT NULL CHECK(risk_level IN ('low', 'medium', 'high', 'critical')),
    var_95 REAL,
    volatility REAL,
    beta REAL,
    max_loss_rate REAL,
    stop_loss_price REAL,
    position_date DATE NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, stock_code, position_date)
);

CREATE INDEX IF NOT EXISTS idx_position_risks_account ON position_risks(account_id);
CREATE INDEX IF NOT EXISTS idx_position_risks_level ON position_risks(risk_level);
CREATE INDEX IF NOT EXISTS idx_position_risks_value ON position_risks(risk_value);
CREATE INDEX IF NOT EXISTS idx_position_risks_date ON position_risks(position_date);

-- ============================================
-- 5. 账户风险指标表
-- ============================================
CREATE TABLE IF NOT EXISTS account_risk_metrics (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    total_value REAL NOT NULL,
    cash_balance REAL NOT NULL,
    position_value REAL NOT NULL,
    liability_value REAL NOT NULL DEFAULT 0,
    leverage_ratio REAL NOT NULL,
    liquidity_ratio REAL NOT NULL,
    risk_score REAL NOT NULL,
    risk_level TEXT NOT NULL CHECK(risk_level IN ('low', 'medium', 'high', 'critical')),
    margin_ratio REAL,
    concentration_ratio REAL,
    net_value REAL,
    daily_return REAL,
    max_drawdown REAL,
    record_date DATE NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, record_date)
);

CREATE INDEX IF NOT EXISTS idx_account_risk_account ON account_risk_metrics(account_id);
CREATE INDEX IF NOT EXISTS idx_account_risk_score ON account_risk_metrics(risk_score);
CREATE INDEX IF NOT EXISTS idx_account_risk_level ON account_risk_metrics(risk_level);
CREATE INDEX IF NOT EXISTS idx_account_risk_date ON account_risk_metrics(record_date);

-- ============================================
-- 6. 主力资金流表
-- ============================================
CREATE TABLE IF NOT EXISTS mainforce_flow (
    id TEXT PRIMARY KEY,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    trade_date DATE NOT NULL,
    main_inflow REAL,
    main_outflow REAL,
    main_netflow REAL,
    main_inflow_ratio REAL,
    retail_inflow REAL,
    total_volume REAL,
    close_price REAL,
    price_change REAL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_mainforce_stock ON mainforce_flow(stock_code);
CREATE INDEX IF NOT EXISTS idx_mainforce_date ON mainforce_flow(trade_date);
CREATE INDEX IF NOT EXISTS idx_mainforce_netflow ON mainforce_flow(main_netflow);

-- ============================================
-- 7. 风控操作日志表
-- ============================================
CREATE TABLE IF NOT EXISTS risk_operation_logs (
    id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL,
    operator_name TEXT,
    operation_type TEXT NOT NULL CHECK(operation_type IN ('create_rule', 'update_rule', 'delete_rule', 'handle_alert', 'confirm_alert', 'ignore_alert', 'process_alert', 'modify_threshold')),
    target_type TEXT NOT NULL CHECK(target_type IN ('rule', 'alert', 'event', 'account')),
    target_id TEXT NOT NULL,
    target_name TEXT,
    old_value TEXT,
    new_value TEXT,
    ip_address TEXT,
    user_agent TEXT,
    result TEXT NOT NULL CHECK(result IN ('success', 'failed')),
    error_message TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_operation_logs_operator ON risk_operation_logs(operator_id);
CREATE INDEX IF NOT EXISTS idx_operation_logs_type ON risk_operation_logs(operation_type);
CREATE INDEX IF NOT EXISTS idx_operation_logs_target ON risk_operation_logs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_operation_logs_created ON risk_operation_logs(created_at);

-- ============================================
-- 插入示例数据
-- ============================================

-- 插入风控规则示例
INSERT OR IGNORE INTO risk_rules (id, name, description, rule_type, condition, action, status, priority, trigger_count) VALUES
('rule_001', '止损规则', '单只股票亏损超过8%时触发止损', 'stop_loss', '{"max_loss_rate": 8}', 'alert', 'active', 100, 156),
('rule_002', '仓位上限规则', '单只股票持仓占比不超过15%', 'position_limit', '{"max_position_ratio": 15}', 'alert', 'active', 90, 89),
('rule_003', '流动性规则', '账户流动性比率不低于1.5', 'liquidity', '{"min_liquidity_ratio": 1.5}', 'alert', 'active', 80, 45),
('rule_004', '杠杆率规则', '总杠杆率不超过2倍', 'leverage', '{"max_leverage": 2.0}', 'block', 'triggered', 95, 23),
('rule_005', '行业集中度规则', '单一行业持仓不超过总仓位的30%', 'concentration', '{"max_industry_ratio": 30}', 'alert', 'inactive', 70, 12);

-- 插入告警示例
INSERT OR IGNORE INTO risk_alerts (id, alert_type, level, stock_code, stock_name, account_id, message, metric_value, threshold_value, status) VALUES
('alert_001', 'stop_loss', 'red', '600519.SH', '贵州茅台', 'acc_001', '股价下跌超过8%，触发止损线', 10.5, 8.0, 'pending'),
('alert_002', 'position_overflow', 'orange', '300750.SZ', '宁德时代', 'acc_001', '持仓占比超过15%上限', 15.5, 15.0, 'pending'),
('alert_003', 'liquidity', 'yellow', '000001.SZ', '平安银行', 'acc_001', '流动性比率低于安全线', 1.2, 1.5, 'confirmed');

-- 插入持仓风险示例
INSERT OR IGNORE INTO position_risks (id, account_id, stock_code, stock_name, position_value, position_ratio, risk_value, risk_level, position_date) VALUES
('pos_001', 'acc_001', '600519.SH', '贵州茅台', 850000, 0.32, 68, 'critical', '2026-05-15'),
('pos_002', 'acc_001', '300750.SZ', '宁德时代', 620000, 0.24, 52, 'high', '2026-05-15'),
('pos_003', 'acc_001', '002594.SZ', '比亚迪', 480000, 0.18, 45, 'high', '2026-05-15'),
('pos_004', 'acc_001', '000001.SZ', '平安银行', 350000, 0.14, 32, 'medium', '2026-05-15'),
('pos_005', 'acc_001', '601318.SH', '中国平安', 280000, 0.12, 28, 'medium', '2026-05-15');

-- 插入账户风险指标示例
INSERT OR IGNORE INTO account_risk_metrics (id, account_id, total_value, cash_balance, position_value, liability_value, leverage_ratio, liquidity_ratio, risk_score, risk_level, record_date) VALUES
('metrics_001', 'acc_001', 2650000, 320000, 2580000, 0, 1.5, 1.8, 65, 'medium', '2026-05-15'),
('metrics_002', 'acc_001', 2700000, 400000, 2300000, 0, 1.4, 2.0, 62, 'medium', '2026-05-14');
