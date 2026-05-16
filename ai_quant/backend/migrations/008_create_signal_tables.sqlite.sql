-- 信号中心数据库表结构 (SQLite版本)
-- 创建时间: 2026-05-15
-- 数据库: risk_management.db (SQLite)

-- 信号规则表
CREATE TABLE IF NOT EXISTS signal_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    logic_type TEXT DEFAULT 'AND',
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 信号规则条件表
CREATE TABLE IF NOT EXISTS signal_rule_conditions (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    indicator TEXT NOT NULL,
    operator TEXT NOT NULL,
    threshold_value REAL DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (rule_id) REFERENCES signal_rules(id) ON DELETE CASCADE
);

-- 信号记录表
CREATE TABLE IF NOT EXISTS signal_records (
    id TEXT PRIMARY KEY,
    stock_code TEXT NOT NULL,
    stock_name TEXT DEFAULT '',
    signal_type TEXT NOT NULL CHECK(signal_type IN ('BUY', 'SELL')),
    strength INTEGER DEFAULT 3,
    score REAL DEFAULT 0,
    reason TEXT,
    macd REAL,
    rsi REAL,
    ma5 REAL,
    ma10 REAL,
    ma20 REAL,
    ma60 REAL,
    close_price REAL NOT NULL,
    boll_upper REAL,
    boll_mid REAL,
    boll_lower REAL,
    trade_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 信号历史快照表
CREATE TABLE IF NOT EXISTS signal_snapshots (
    id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL,
    snapshot_data TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (signal_id) REFERENCES signal_records(id) ON DELETE CASCADE
);

-- 信号统计表
CREATE TABLE IF NOT EXISTS signal_statistics (
    id TEXT PRIMARY KEY,
    stat_date TEXT NOT NULL,
    stat_type TEXT NOT NULL CHECK(stat_type IN ('DAILY', 'WEEKLY', 'MONTHLY')),
    buy_count INTEGER DEFAULT 0,
    sell_count INTEGER DEFAULT 0,
    avg_strength REAL DEFAULT 0,
    top_stocks TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(stat_date, stat_type)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_signal_stock_code ON signal_records(stock_code);
CREATE INDEX IF NOT EXISTS idx_signal_type ON signal_records(signal_type);
CREATE INDEX IF NOT EXISTS idx_signal_strength ON signal_records(strength);
CREATE INDEX IF NOT EXISTS idx_signal_trade_date ON signal_records(trade_date);
CREATE INDEX IF NOT EXISTS idx_signal_created_at ON signal_records(created_at);
CREATE INDEX IF NOT EXISTS idx_rule_conditions_rule_id ON signal_rule_conditions(rule_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_signal_id ON signal_snapshots(signal_id);
CREATE INDEX IF NOT EXISTS idx_stats_date ON signal_statistics(stat_date);

-- 插入示例信号规则
INSERT OR IGNORE INTO signal_rules (id, name, description, logic_type, enabled) VALUES
('rule_001', 'RSI超卖买入规则', '当RSI低于30时产生买入信号', 'AND', 1),
('rule_002', 'MACD金叉买入规则', '当MACD上穿0轴时产生买入信号', 'AND', 1),
('rule_003', '布林带下轨买入规则', '价格跌破布林下轨时产生买入信号', 'AND', 1);

-- 插入示例规则条件
INSERT OR IGNORE INTO signal_rule_conditions (id, rule_id, indicator, operator, threshold_value, sort_order) VALUES
('cond_001', 'rule_001', 'rsi14', '<', 30, 0),
('cond_002', 'rule_002', 'macd_hist', 'cross_up', 0, 0),
('cond_003', 'rule_003', 'boll_lower', 'cross_down', 0, 0);

-- 插入示例信号数据
INSERT OR IGNORE INTO signal_records (id, stock_code, stock_name, signal_type, strength, score, reason, macd, rsi, ma20, close_price, trade_date) VALUES
('sig_001', '600519.SH', '贵州茅台', 'BUY', 5, 88.5, 'RSI超卖，MACD金叉', 0.85, 28.5, 1680.50, 1720.80, date('now')),
('sig_002', '300750.SZ', '宁德时代', 'BUY', 4, 76.0, '价格上穿MA20', 0.45, 35.2, 198.20, 205.50, date('now')),
('sig_003', '002594.SZ', '比亚迪', 'SELL', 4, 72.0, 'RSI超买', -0.95, 75.8, 268.50, 258.30, date('now')),
('sig_004', '688041.SH', '寒武纪', 'BUY', 5, 85.0, 'MACD金叉，RSI超卖', 1.25, 25.4, 128.30, 138.90, date('now')),
('sig_005', '601318.SH', '中国平安', 'SELL', 3, 68.0, '价格跌破布林中轨', -0.35, 68.5, 42.80, 41.20, date('now'));
