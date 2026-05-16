-- 信号中心数据库表结构
-- 创建时间: 2026-05-15

-- 信号规则表
CREATE TABLE IF NOT EXISTS signal_rules (
    id VARCHAR(64) PRIMARY KEY COMMENT '规则ID',
    name VARCHAR(255) NOT NULL COMMENT '规则名称',
    description TEXT COMMENT '规则描述',
    logic_type ENUM('AND', 'OR') DEFAULT 'AND' COMMENT '条件逻辑：AND或OR',
    enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='信号规则表';

-- 信号规则条件表
CREATE TABLE IF NOT EXISTS signal_rule_conditions (
    id VARCHAR(64) PRIMARY KEY COMMENT '条件ID',
    rule_id VARCHAR(64) NOT NULL COMMENT '关联规则ID',
    indicator VARCHAR(64) NOT NULL COMMENT '指标名称',
    operator VARCHAR(32) NOT NULL COMMENT '操作符',
    threshold_value DECIMAL(20, 4) DEFAULT 0 COMMENT '阈值',
    sort_order INT DEFAULT 0 COMMENT '排序顺序',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (rule_id) REFERENCES signal_rules(id) ON DELETE CASCADE,
    INDEX idx_rule_id (rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='信号规则条件表';

-- 信号记录表
CREATE TABLE IF NOT EXISTS signal_records (
    id VARCHAR(64) PRIMARY KEY COMMENT '信号ID',
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(128) DEFAULT '' COMMENT '股票名称',
    signal_type ENUM('BUY', 'SELL') NOT NULL COMMENT '信号类型',
    strength INT DEFAULT 3 COMMENT '信号强度 1-5',
    score DECIMAL(10, 2) DEFAULT 0 COMMENT '信号评分 0-100',
    reason TEXT COMMENT '信号原因',
    macd DECIMAL(20, 4) DEFAULT NULL COMMENT 'MACD值',
    rsi DECIMAL(10, 2) DEFAULT NULL COMMENT 'RSI值',
    ma5 DECIMAL(20, 4) DEFAULT NULL COMMENT 'MA5值',
    ma10 DECIMAL(20, 4) DEFAULT NULL COMMENT 'MA10值',
    ma20 DECIMAL(20, 4) DEFAULT NULL COMMENT 'MA20值',
    ma60 DECIMAL(20, 4) DEFAULT NULL COMMENT 'MA60值',
    close_price DECIMAL(20, 4) NOT NULL COMMENT '收盘价',
    boll_upper DECIMAL(20, 4) DEFAULT NULL COMMENT '布林上轨',
    boll_mid DECIMAL(20, 4) DEFAULT NULL COMMENT '布林中轨',
    boll_lower DECIMAL(20, 4) DEFAULT NULL COMMENT '布林下轨',
    trade_date DATE NOT NULL COMMENT '交易日期',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_stock_code (stock_code),
    INDEX idx_signal_type (signal_type),
    INDEX idx_strength (strength),
    INDEX idx_trade_date (trade_date),
    INDEX idx_created_at (created_at),
    INDEX idx_composite (trade_date, signal_type, strength)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='信号记录表';

-- 信号历史快照表（用于回测和分析）
CREATE TABLE IF NOT EXISTS signal_snapshots (
    id VARCHAR(64) PRIMARY KEY COMMENT '快照ID',
    signal_id VARCHAR(64) NOT NULL COMMENT '关联信号ID',
    snapshot_data JSON COMMENT '技术指标快照JSON',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (signal_id) REFERENCES signal_records(id) ON DELETE CASCADE,
    INDEX idx_signal_id (signal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='信号历史快照表';

-- 信号统计表（日/周/月）
CREATE TABLE IF NOT EXISTS signal_statistics (
    id VARCHAR(64) PRIMARY KEY COMMENT '统计ID',
    stat_date DATE NOT NULL COMMENT '统计日期',
    stat_type ENUM('DAILY', 'WEEKLY', 'MONTHLY') NOT NULL COMMENT '统计类型',
    buy_count INT DEFAULT 0 COMMENT '买入信号数量',
    sell_count INT DEFAULT 0 COMMENT '卖出信号数量',
    avg_strength DECIMAL(5, 2) DEFAULT 0 COMMENT '平均信号强度',
    top_stocks JSON COMMENT '热门股票JSON',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uk_date_type (stat_date, stat_type),
    INDEX idx_stat_date (stat_date),
    INDEX idx_stat_type (stat_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='信号统计表';
