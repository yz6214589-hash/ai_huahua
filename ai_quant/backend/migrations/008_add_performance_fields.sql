-- AI量化交易系统 - 字段扩充脚本
-- 基于现有表结构，添加绩效报告相关字段

-- ============================================
-- 1. 扩充 trade_stock_info 表
-- ============================================
ALTER TABLE trade_stock_info
ADD COLUMN IF NOT EXISTS pe_ratio DECIMAL(10, 2) DEFAULT NULL COMMENT '市盈率（TTM）' AFTER market,
ADD COLUMN IF NOT EXISTS pb_ratio DECIMAL(10, 2) DEFAULT NULL COMMENT '市净率（MRQ）' AFTER pe_ratio,
ADD COLUMN IF NOT EXISTS market_cap BIGINT DEFAULT NULL COMMENT '总市值（元）' AFTER pb_ratio,
ADD COLUMN IF NOT EXISTS float_market_cap BIGINT DEFAULT NULL COMMENT '流通市值（元）' AFTER market_cap,
ADD INDEX idx_pe (pe_ratio),
ADD INDEX idx_market_cap (market_cap);

-- ============================================
-- 2. 扩充 trade_stock_daily 表
-- ============================================
ALTER TABLE trade_stock_daily
ADD COLUMN IF NOT EXISTS turnover_rate DECIMAL(10, 4) DEFAULT NULL COMMENT '换手率(%)' AFTER change_pct,
ADD COLUMN IF NOT EXISTS pe_ratio DECIMAL(10, 2) DEFAULT NULL COMMENT '市盈率' AFTER turnover_rate,
ADD COLUMN IF NOT EXISTS pb_ratio DECIMAL(10, 2) DEFAULT NULL COMMENT '市净率' AFTER pe_ratio,
ADD COLUMN IF NOT EXISTS amplitude DECIMAL(10, 4) DEFAULT NULL COMMENT '振幅(%)' AFTER pb_ratio;

-- ============================================
-- 3. 扩充 signal_records 表
-- ============================================
ALTER TABLE signal_records
ADD COLUMN IF NOT EXISTS strategy_name VARCHAR(128) DEFAULT NULL COMMENT '策略名称' AFTER reason,
ADD COLUMN IF NOT EXISTS backtest_id VARCHAR(64) DEFAULT NULL COMMENT '关联回测ID' AFTER strategy_name,
ADD COLUMN IF NOT EXISTS trigger_price DECIMAL(20, 4) DEFAULT NULL COMMENT '触发价格' AFTER close_price,
ADD COLUMN IF NOT EXISTS target_price DECIMAL(20, 4) DEFAULT NULL COMMENT '目标价格' AFTER trigger_price,
ADD COLUMN IF NOT EXISTS stop_loss_price DECIMAL(20, 4) DEFAULT NULL COMMENT '止损价格' AFTER target_price,
ADD COLUMN IF NOT EXISTS status ENUM('pending', 'triggered', 'expired', 'cancelled') DEFAULT 'pending' COMMENT '信号状态' AFTER trade_date,
ADD COLUMN IF NOT EXISTS expired_at DATETIME DEFAULT NULL COMMENT '过期时间' AFTER status,
ADD INDEX idx_backtest_id (backtest_id),
ADD INDEX idx_status (status);

-- ============================================
-- 4. 扩充 signal_rules 表
-- ============================================
ALTER TABLE signal_rules
ADD COLUMN IF NOT EXISTS strategy_type VARCHAR(50) DEFAULT NULL COMMENT '策略类型' AFTER description,
ADD COLUMN IF NOT EXISTS strategy_params JSON DEFAULT NULL COMMENT '策略参数JSON' AFTER strategy_type,
ADD COLUMN IF NOT EXISTS priority INT DEFAULT 0 COMMENT '优先级' AFTER enabled,
ADD COLUMN IF NOT EXISTS min_strength INT DEFAULT 1 COMMENT '最小信号强度' AFTER priority,
ADD COLUMN IF NOT EXISTS max_positions INT DEFAULT 10 COMMENT '最大持仓数' AFTER min_strength;

-- ============================================
-- 5. 新增回测记录表
-- ============================================
CREATE TABLE IF NOT EXISTS backtest_records (
    id VARCHAR(64) PRIMARY KEY COMMENT '回测ID',
    strategy_name VARCHAR(100) NOT NULL COMMENT '策略名称',
    strategy_type VARCHAR(50) NOT NULL COMMENT '策略类型',
    strategy_params JSON COMMENT '策略参数JSON',

    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    start_date DATE NOT NULL COMMENT '开始日期',
    end_date DATE NOT NULL COMMENT '结束日期',

    initial_cash DECIMAL(15, 2) NOT NULL COMMENT '初始资金',
    final_capital DECIMAL(15, 2) NOT NULL COMMENT '最终资金',
    total_return DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '总收益率(%)',
    annualized_return DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '年化收益率(%)',
    max_drawdown DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '最大回撤(%)',
    sharpe_ratio DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '夏普比率',

    total_trades INT DEFAULT 0 COMMENT '总交易次数',
    winning_trades INT DEFAULT 0 COMMENT '盈利次数',
    losing_trades INT DEFAULT 0 COMMENT '亏损次数',

    nav_data JSON COMMENT '净值数据JSON',
    trades_data JSON COMMENT '交易数据JSON',

    status ENUM('running', 'completed', 'failed') DEFAULT 'running' COMMENT '状态',
    error_message TEXT COMMENT '错误信息',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_strategy_name (strategy_name),
    INDEX idx_stock_code (stock_code),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测记录表';

-- ============================================
-- 6. 新增绩效报告表
-- ============================================
CREATE TABLE IF NOT EXISTS performance_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    report_id VARCHAR(64) NOT NULL COMMENT '报告ID',
    report_type ENUM('common', 'plus') NOT NULL COMMENT '报告类型',

    strategy_name VARCHAR(100) NOT NULL COMMENT '策略名称',
    backtest_id VARCHAR(64) DEFAULT NULL COMMENT '关联回测ID',

    start_date DATE NOT NULL COMMENT '开始日期',
    end_date DATE NOT NULL COMMENT '结束日期',
    initial_cash DECIMAL(15, 2) NOT NULL COMMENT '初始资金',
    final_nav DECIMAL(15, 4) NOT NULL COMMENT '最终净值',

    -- 收益指标
    total_return DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '总收益率(%)',
    annualized_return DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '年化收益率(%)',
    benchmark_return DECIMAL(10, 4) DEFAULT NULL COMMENT '基准收益率(%)',
    excess_return DECIMAL(10, 4) DEFAULT NULL COMMENT '超额收益率(%)',

    -- 风险指标
    max_drawdown DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '最大回撤(%)',
    volatility DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '波动率(%)',
    sharpe_ratio DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '夏普比率',
    calmar_ratio DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '卡玛比率',
    sortino_ratio DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '索提诺比率',

    -- 交易统计
    total_trades INT DEFAULT 0 COMMENT '总交易次数',
    winning_trades INT DEFAULT 0 COMMENT '盈利次数',
    losing_trades INT DEFAULT 0 COMMENT '亏损次数',
    win_rate DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '胜率(%)',
    profit_factor DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '盈利因子',

    -- 扩展数据
    chart_data JSON COMMENT '图表数据JSON',
    monthly_returns JSON COMMENT '月度收益JSON',

    status ENUM('pending', 'generated', 'failed') DEFAULT 'pending' COMMENT '状态',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_report_id (report_id),
    INDEX idx_backtest_id (backtest_id),
    INDEX idx_strategy_name (strategy_name),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='绩效报告表';

-- ============================================
-- 7. 新增模拟账户表
-- ============================================
CREATE TABLE IF NOT EXISTS sim_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_name VARCHAR(100) NOT NULL COMMENT '账户名称',
    initial_capital DECIMAL(15, 2) NOT NULL COMMENT '初始资金',
    current_capital DECIMAL(15, 2) NOT NULL COMMENT '当前可用资金',
    market_value DECIMAL(15, 2) DEFAULT 0.00 COMMENT '持仓市值',
    total_asset DECIMAL(15, 2) NOT NULL COMMENT '总资产',

    total_pnl DECIMAL(15, 2) DEFAULT 0.00 COMMENT '总盈亏',
    total_pnl_pct DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '总盈亏比例(%)',
    today_pnl DECIMAL(15, 2) DEFAULT 0.00 COMMENT '今日盈亏',
    today_pnl_pct DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '今日盈亏比例(%)',

    position_count INT DEFAULT 0 COMMENT '持仓数量',
    status ENUM('active', 'closed') DEFAULT 'active' COMMENT '状态',
    description TEXT COMMENT '账户描述',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_account_name (account_name),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟账户表';

-- ============================================
-- 8. 新增模拟账户持仓表
-- ============================================
CREATE TABLE IF NOT EXISTS sim_positions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL COMMENT '账户ID',
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(100) NOT NULL COMMENT '股票名称',

    volume INT NOT NULL COMMENT '持仓数量',
    cost DECIMAL(15, 4) NOT NULL COMMENT '成本价',
    cur_price DECIMAL(15, 4) NOT NULL COMMENT '当前价格',
    market_value DECIMAL(15, 2) NOT NULL COMMENT '市值',
    pnl DECIMAL(15, 2) NOT NULL COMMENT '盈亏金额',
    pnl_pct DECIMAL(10, 4) NOT NULL COMMENT '盈亏比例(%)',

    available_volume INT NOT NULL COMMENT '可用数量',
    position_type ENUM('normal', 'locked') DEFAULT 'normal' COMMENT '持仓类型',
    buy_date DATE COMMENT '买入日期',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_account_id (account_id),
    INDEX idx_stock_code (stock_code),
    FOREIGN KEY (account_id) REFERENCES sim_accounts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟账户持仓表';

-- ============================================
-- 9. 新增模拟账户交易记录表
-- ============================================
CREATE TABLE IF NOT EXISTS sim_trades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trade_no VARCHAR(64) NOT NULL COMMENT '交易编号',
    account_id INT NOT NULL COMMENT '账户ID',
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(100) NOT NULL COMMENT '股票名称',

    side ENUM('buy', 'sell') NOT NULL COMMENT '买卖方向',
    price DECIMAL(15, 4) NOT NULL COMMENT '成交价格',
    volume INT NOT NULL COMMENT '成交数量',
    amount DECIMAL(15, 2) NOT NULL COMMENT '成交金额',
    commission DECIMAL(10, 2) DEFAULT 0.00 COMMENT '手续费',

    trade_time DATETIME NOT NULL COMMENT '成交时间',
    strategy VARCHAR(100) COMMENT '策略名称',
    backtest_id VARCHAR(64) COMMENT '关联回测ID',
    remark TEXT COMMENT '备注',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY uk_trade_no (trade_no),
    INDEX idx_account_id (account_id),
    INDEX idx_stock_code (stock_code),
    INDEX idx_trade_time (trade_time),
    INDEX idx_backtest_id (backtest_id),
    FOREIGN KEY (account_id) REFERENCES sim_accounts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟账户交易记录表';
