-- 主力识别功能数据库迁移脚本
-- 手动执行此脚本以创建主力识别相关的数据表

-- 主力活动记录表
CREATE TABLE IF NOT EXISTS mainforce_activities (
    id TEXT PRIMARY KEY,
    date DATE NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    volume INTEGER NOT NULL,
    amount REAL NOT NULL,
    price REAL NOT NULL,
    ratio REAL NOT NULL,
    mainforce_type TEXT NOT NULL DEFAULT 'retail',
    description TEXT,
    indicators TEXT,
    is_anomaly INTEGER NOT NULL DEFAULT 0,
    alert_status TEXT NOT NULL DEFAULT 'none',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ma_date ON mainforce_activities(date);
CREATE INDEX IF NOT EXISTS idx_ma_stock_code ON mainforce_activities(stock_code);
CREATE INDEX IF NOT EXISTS idx_ma_activity_type ON mainforce_activities(activity_type);

-- 主力识别任务表
CREATE TABLE IF NOT EXISTS mainforce_tasks (
    id TEXT PRIMARY KEY,
    stock_code TEXT NOT NULL,
    company_name TEXT,
    mode TEXT NOT NULL DEFAULT 'simulated',
    params TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    error_message TEXT,
    triggered_rule_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mt_stock_code ON mainforce_tasks(stock_code);
CREATE INDEX IF NOT EXISTS idx_mt_status ON mainforce_tasks(status);

-- 主力持仓变化表
CREATE TABLE IF NOT EXISTS mainforce_position_changes (
    id TEXT PRIMARY KEY,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    position_date DATE NOT NULL,
    position_ratio REAL NOT NULL,
    position_change REAL NOT NULL,
    position_value REAL,
    change_type TEXT NOT NULL,
    reason TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_code, position_date)
);

CREATE INDEX IF NOT EXISTS idx_mpc_stock_code ON mainforce_position_changes(stock_code);

-- K线标注表
CREATE TABLE IF NOT EXISTS kline_markers (
    id TEXT PRIMARY KEY,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    marker_date DATE NOT NULL,
    marker_price REAL NOT NULL,
    marker_type TEXT NOT NULL,
    volume INTEGER,
    amount REAL,
    mainforce_type TEXT NOT NULL DEFAULT 'retail',
    source TEXT NOT NULL DEFAULT 'auto',
    activity_id TEXT,
    description TEXT,
    is_visible INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_code, marker_date, marker_type)
);

CREATE INDEX IF NOT EXISTS idx_km_stock_code ON kline_markers(stock_code);

-- 主力告警规则表
CREATE TABLE IF NOT EXISTS mainforce_alert_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    description TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    threshold REAL NOT NULL,
    threshold_unit TEXT,
    condition TEXT,
    action TEXT NOT NULL DEFAULT 'alert',
    priority INTEGER NOT NULL DEFAULT 0,
    trigger_count INTEGER NOT NULL DEFAULT 0,
    last_trigger_time DATETIME,
    last_trigger_value REAL,
    alert_template TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_mar_enabled ON mainforce_alert_rules(enabled);

-- 主力识别统计表
CREATE TABLE IF NOT EXISTS mainforce_statistics (
    id TEXT PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    buy_count INTEGER NOT NULL DEFAULT 0,
    sell_count INTEGER NOT NULL DEFAULT 0,
    total_buy_amount REAL NOT NULL DEFAULT 0,
    total_sell_amount REAL NOT NULL DEFAULT 0,
    net_flow REAL NOT NULL DEFAULT 0,
    institution_buy_count INTEGER NOT NULL DEFAULT 0,
    hot_money_buy_count INTEGER NOT NULL DEFAULT 0,
    retail_sell_count INTEGER NOT NULL DEFAULT 0,
    anomaly_count INTEGER NOT NULL DEFAULT 0,
    alert_count INTEGER NOT NULL DEFAULT 0,
    top_stocks TEXT,
    summary TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
