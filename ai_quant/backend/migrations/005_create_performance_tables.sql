-- 绩效报告表
-- 用于存储生成的绩效报告

CREATE TABLE IF NOT EXISTS `performance_report` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `report_id` VARCHAR(64) NOT NULL COMMENT '报告ID',
  `report_type` VARCHAR(20) NOT NULL COMMENT '报告类型：common/plus',
  `strategy_name` VARCHAR(100) NOT NULL COMMENT '策略名称',
  `strategy_params` TEXT COMMENT '策略参数JSON',
  `backtest_id` VARCHAR(64) COMMENT '关联的回测ID',

  `start_date` DATE NOT NULL COMMENT '开始日期',
  `end_date` DATE NOT NULL COMMENT '结束日期',
  `initial_cash` DECIMAL(15, 2) NOT NULL COMMENT '初始资金',
  `final_nav` DECIMAL(15, 4) NOT NULL COMMENT '最终净值',
  `benchmark_code` VARCHAR(20) COMMENT '基准代码',

  `total_return` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '总收益率(%)',
  `annualized_return` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '年化收益率(%)',
  `max_drawdown` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '最大回撤(%)',
  `volatility` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '波动率(%)',
  `sharpe_ratio` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '夏普比率',
  `calmar_ratio` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '卡玛比率',
  `win_rate` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '胜率(%)',
  `profit_factor` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '盈利因子',

  `total_trades` INT DEFAULT 0 COMMENT '总交易次数',
  `winning_trades` INT DEFAULT 0 COMMENT '盈利次数',
  `losing_trades` INT DEFAULT 0 COMMENT '亏损次数',

  `chart_data` MEDIUMTEXT COMMENT '图表数据JSON',
  `trades_data` MEDIUMTEXT COMMENT '交易记录JSON',

  `status` VARCHAR(20) DEFAULT 'pending' COMMENT '状态：pending/completed/failed',
  `error_message` TEXT COMMENT '错误信息',

  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_id` (`report_id`),
  KEY `idx_strategy_name` (`strategy_name`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='绩效报告表';


-- 回测记录表
-- 用于存储回测执行记录

CREATE TABLE IF NOT EXISTS `backtest_record` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `backtest_id` VARCHAR(64) NOT NULL COMMENT '回测ID',
  `strategy_name` VARCHAR(100) NOT NULL COMMENT '策略名称',
  `strategy_type` VARCHAR(50) NOT NULL COMMENT '策略类型',
  `strategy_params` TEXT COMMENT '策略参数JSON',

  `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
  `start_date` DATE NOT NULL COMMENT '开始日期',
  `end_date` DATE NOT NULL COMMENT '结束日期',

  `initial_cash` DECIMAL(15, 2) NOT NULL COMMENT '初始资金',
  `final_capital` DECIMAL(15, 2) NOT NULL COMMENT '最终资金',
  `total_return` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '总收益率(%)',
  `annualized_return` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '年化收益率(%)',
  `max_drawdown` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '最大回撤(%)',
  `sharpe_ratio` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '夏普比率',

  `total_trades` INT DEFAULT 0 COMMENT '总交易次数',
  `winning_trades` INT DEFAULT 0 COMMENT '盈利次数',
  `losing_trades` INT DEFAULT 0 COMMENT '亏损次数',

  `nav_data` MEDIUMTEXT COMMENT '净值数据JSON',
  `trades_data` MEDIUMTEXT COMMENT '交易数据JSON',

  `status` VARCHAR(20) DEFAULT 'running' COMMENT '状态：running/completed/failed',
  `error_message` TEXT COMMENT '错误信息',

  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_backtest_id` (`backtest_id`),
  KEY `idx_strategy_name` (`strategy_name`),
  KEY `idx_stock_code` (`stock_code`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测记录表';


-- 模拟账户表
-- 用于存储模拟盘账户信息

CREATE TABLE IF NOT EXISTS `sim_account` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `account_name` VARCHAR(100) NOT NULL COMMENT '账户名称',
  `initial_capital` DECIMAL(15, 2) NOT NULL COMMENT '初始资金',
  `current_capital` DECIMAL(15, 2) NOT NULL COMMENT '当前可用资金',
  `market_value` DECIMAL(15, 2) DEFAULT 0.00 COMMENT '持仓市值',
  `total_asset` DECIMAL(15, 2) NOT NULL COMMENT '总资产',
  `total_pnl` DECIMAL(15, 2) DEFAULT 0.00 COMMENT '总盈亏',
  `total_pnl_pct` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '总盈亏比例(%)',
  `today_pnl` DECIMAL(15, 2) DEFAULT 0.00 COMMENT '今日盈亏',
  `today_pnl_pct` DECIMAL(10, 4) DEFAULT 0.0000 COMMENT '今日盈亏比例(%)',
  `position_count` INT DEFAULT 0 COMMENT '持仓数量',
  `status` VARCHAR(20) DEFAULT 'active' COMMENT '状态：active/closed',
  `description` TEXT COMMENT '账户描述',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

  PRIMARY KEY (`id`),
  KEY `idx_account_name` (`account_name`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟账户表';


-- 模拟账户持仓表
-- 用于存储模拟盘持仓信息

CREATE TABLE IF NOT EXISTS `sim_position` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `account_id` INT NOT NULL COMMENT '账户ID',
  `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
  `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
  `volume` INT NOT NULL COMMENT '持仓数量',
  `cost` DECIMAL(15, 4) NOT NULL COMMENT '成本价',
  `cur_price` DECIMAL(15, 4) NOT NULL COMMENT '当前价格',
  `market_value` DECIMAL(15, 2) NOT NULL COMMENT '市值',
  `pnl` DECIMAL(15, 2) NOT NULL COMMENT '盈亏金额',
  `pnl_pct` DECIMAL(10, 4) NOT NULL COMMENT '盈亏比例(%)',
  `available_volume` INT NOT NULL COMMENT '可用数量',
  `position_type` VARCHAR(20) DEFAULT 'normal' COMMENT '持仓类型：normal/locked',
  `buy_date` DATE COMMENT '买入日期',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

  PRIMARY KEY (`id`),
  KEY `idx_account_id` (`account_id`),
  KEY `idx_stock_code` (`stock_code`),
  KEY `idx_created_at` (`created_at`),
  FOREIGN KEY (`account_id`) REFERENCES `sim_account`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟账户持仓表';


-- 模拟账户交易记录表
-- 用于存储模拟盘交易记录

CREATE TABLE IF NOT EXISTS `sim_trade` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `trade_no` VARCHAR(64) NOT NULL COMMENT '交易编号',
  `account_id` INT NOT NULL COMMENT '账户ID',
  `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
  `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
  `side` VARCHAR(10) NOT NULL COMMENT '买卖方向：buy/sell',
  `price` DECIMAL(15, 4) NOT NULL COMMENT '成交价格',
  `volume` INT NOT NULL COMMENT '成交数量',
  `amount` DECIMAL(15, 2) NOT NULL COMMENT '成交金额',
  `commission` DECIMAL(10, 2) DEFAULT 0.00 COMMENT '手续费',
  `account_type` VARCHAR(20) DEFAULT 'sim' COMMENT '账户类型：sim/real',
  `trade_time` DATETIME NOT NULL COMMENT '成交时间',
  `strategy` VARCHAR(100) COMMENT '策略名称',
  `remark` TEXT COMMENT '备注',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_trade_no` (`trade_no`),
  KEY `idx_account_id` (`account_id`),
  KEY `idx_stock_code` (`stock_code`),
  KEY `idx_trade_time` (`trade_time`),
  KEY `idx_side` (`side`),
  FOREIGN KEY (`account_id`) REFERENCES `sim_account`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟账户交易记录表';


-- 信号规则表
-- 用于存储信号规则配置

CREATE TABLE IF NOT EXISTS `signal_rule` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `rule_name` VARCHAR(100) NOT NULL COMMENT '规则名称',
  `rule_type` VARCHAR(50) NOT NULL COMMENT '规则类型',
  `conditions` JSON NOT NULL COMMENT '条件JSON',
  `logic` VARCHAR(10) DEFAULT 'AND' COMMENT '逻辑关系：AND/OR',
  `enabled` TINYINT(1) DEFAULT 1 COMMENT '是否启用：0-禁用 1-启用',
  `priority` INT DEFAULT 0 COMMENT '优先级',
  `description` TEXT COMMENT '规则描述',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

  PRIMARY KEY (`id`),
  KEY `idx_rule_type` (`rule_type`),
  KEY `idx_enabled` (`enabled`),
  KEY `idx_priority` (`priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='信号规则表';


-- 信号记录表
-- 用于存储生成的交易信号

CREATE TABLE IF NOT EXISTS `signal_record` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `signal_id` VARCHAR(64) NOT NULL COMMENT '信号ID',
  `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
  `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
  `signal_type` VARCHAR(10) NOT NULL COMMENT '信号类型：BUY/SELL',
  `strength` INT DEFAULT 3 COMMENT '信号强度 1-5',
  `score` DECIMAL(5, 2) DEFAULT 0.00 COMMENT '评分',
  `price` DECIMAL(15, 4) COMMENT '信号价格',
  `reason` TEXT COMMENT '信号原因',
  `rule_id` INT COMMENT '触发规则ID',
  `status` VARCHAR(20) DEFAULT 'pending' COMMENT '状态：pending/triggered/expired/cancelled',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `expired_at` DATETIME COMMENT '过期时间',

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_signal_id` (`signal_id`),
  KEY `idx_stock_code` (`stock_code`),
  KEY `idx_signal_type` (`signal_type`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`),
  FOREIGN KEY (`rule_id`) REFERENCES `signal_rule`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='信号记录表';
