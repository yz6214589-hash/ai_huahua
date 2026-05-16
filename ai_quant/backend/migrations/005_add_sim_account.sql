-- =============================================================================
-- AI 量化投资系统 - 数据库迁移脚本 (V005)
-- 版本: 5.0
-- 创建日期: 2026-05-15
-- 作者: AI 助手
-- 描述: 创建模拟盘账户相关表（账户表、持仓表、交易记录表）
-- =============================================================================

SELECT '====================================' AS '';
SELECT '开始执行数据库迁移 V005' AS '迁移状态';
SELECT '执行时间:' AS '', NOW() AS '';

-- -----------------------------------------------------------------------------
-- 创建模拟盘账户表
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `sim_account` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `account_name` VARCHAR(100) NOT NULL COMMENT '账户名称',
    `initial_capital` DECIMAL(15, 2) NOT NULL DEFAULT 1000000.00 COMMENT '初始资金（元）',
    `current_capital` DECIMAL(15, 2) NOT NULL DEFAULT 1000000.00 COMMENT '当前可用资金（元）',
    `market_value` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '持仓市值（元）',
    `total_asset` DECIMAL(15, 2) NOT NULL DEFAULT 1000000.00 COMMENT '总资产（元）',
    `total_pnl` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '累计收益（元）',
    `total_pnl_pct` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000 COMMENT '累计收益率（%）',
    `today_pnl` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '当日收益（元）',
    `today_pnl_pct` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000 COMMENT '当日收益率（%）',
    `position_count` INT NOT NULL DEFAULT 0 COMMENT '持仓数量',
    `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '账户状态：active-活跃、frozen-冻结、closed-关闭',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `last_reset_at` DATETIME DEFAULT NULL COMMENT '最后重置时间',
    `description` VARCHAR(500) DEFAULT NULL COMMENT '账户描述',
    UNIQUE KEY `uk_account_name` (`account_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟盘账户表';

-- -----------------------------------------------------------------------------
-- 创建模拟盘持仓表
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `sim_position` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `account_id` INT NOT NULL COMMENT '账户ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
    `volume` INT NOT NULL DEFAULT 0 COMMENT '持有数量',
    `cost` DECIMAL(15, 4) NOT NULL DEFAULT 0.00 COMMENT '成本价（元）',
    `cur_price` DECIMAL(15, 4) NOT NULL DEFAULT 0.00 COMMENT '当前价（元）',
    `market_value` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '市值（元）',
    `pnl` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '浮动盈亏（元）',
    `pnl_pct` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000 COMMENT '盈亏比例（%）',
    `today_pnl` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '当日盈亏（元）',
    `today_pnl_pct` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000 COMMENT '当日盈亏比例（%）',
    `available_volume` INT NOT NULL DEFAULT 0 COMMENT '可用数量',
    `frozen_volume` INT NOT NULL DEFAULT 0 COMMENT '冻结数量（挂单中）',
    `position_type` VARCHAR(20) NOT NULL DEFAULT 'sim' COMMENT '持仓类型：sim-模拟盘、real-实盘',
    `buy_date` DATE DEFAULT NULL COMMENT '买入日期',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_account_stock` (`account_id`, `stock_code`),
    KEY `idx_stock_code` (`stock_code`),
    KEY `idx_position_type` (`position_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟盘持仓表';

-- -----------------------------------------------------------------------------
-- 创建模拟盘交易记录表
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `sim_trade` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `account_id` INT NOT NULL COMMENT '账户ID',
    `trade_no` VARCHAR(50) NOT NULL COMMENT '成交编号',
    `order_no` VARCHAR(50) DEFAULT NULL COMMENT '委托编号',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
    `side` VARCHAR(10) NOT NULL COMMENT '交易方向：buy-买入、sell-卖出',
    `price` DECIMAL(15, 4) NOT NULL COMMENT '成交价格（元）',
    `volume` INT NOT NULL COMMENT '成交数量',
    `amount` DECIMAL(15, 2) NOT NULL COMMENT '成交金额（元）',
    `commission` DECIMAL(10, 2) NOT NULL DEFAULT 0.00 COMMENT '手续费（元）',
    `account_type` VARCHAR(20) NOT NULL DEFAULT 'sim' COMMENT '账户类型：sim-模拟盘、real-实盘',
    `status` VARCHAR(20) NOT NULL DEFAULT 'filled' COMMENT '订单状态：pending-待成交、partial-部分成交、filled-全部成交、cancelled-已撤单、rejected-已拒绝',
    `trade_time` DATETIME NOT NULL COMMENT '成交时间',
    `order_time` DATETIME DEFAULT NULL COMMENT '委托时间',
    `strategy` VARCHAR(50) DEFAULT NULL COMMENT '策略名称',
    `remark` VARCHAR(500) DEFAULT NULL COMMENT '备注',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY `uk_trade_no` (`trade_no`),
    KEY `idx_account_id` (`account_id`),
    KEY `idx_stock_code` (`stock_code`),
    KEY `idx_side` (`side`),
    KEY `idx_account_type` (`account_type`),
    KEY `idx_trade_time` (`trade_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟盘交易记录表';

-- -----------------------------------------------------------------------------
-- 创建模拟盘持仓历史表（用于计算收益曲线）
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `sim_position_history` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `account_id` INT NOT NULL COMMENT '账户ID',
    `record_date` DATE NOT NULL COMMENT '记录日期',
    `total_asset` DECIMAL(15, 2) NOT NULL COMMENT '当日总资产（元）',
    `market_value` DECIMAL(15, 2) NOT NULL COMMENT '当日持仓市值（元）',
    `cash` DECIMAL(15, 2) NOT NULL COMMENT '当日现金（元）',
    `total_pnl` DECIMAL(15, 2) NOT NULL COMMENT '累计收益（元）',
    `total_pnl_pct` DECIMAL(10, 4) NOT NULL COMMENT '累计收益率（%）',
    `day_pnl` DECIMAL(15, 2) NOT NULL COMMENT '当日收益（元）',
    `day_pnl_pct` DECIMAL(10, 4) NOT NULL COMMENT '当日收益率（%）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY `uk_account_date` (`account_id`, `record_date`),
    KEY `idx_record_date` (`record_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟盘持仓历史表';

-- -----------------------------------------------------------------------------
-- 迁移完成校验
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '校验新增表...' AS '校验阶段';

SELECT 'sim_account' AS tbl, COUNT(*) AS exists_flag
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name = 'sim_account'
UNION ALL
SELECT 'sim_position' AS tbl, COUNT(*) AS exists_flag
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name = 'sim_position'
UNION ALL
SELECT 'sim_trade' AS tbl, COUNT(*) AS exists_flag
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name = 'sim_trade'
UNION ALL
SELECT 'sim_position_history' AS tbl, COUNT(*) AS exists_flag
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name = 'sim_position_history';

-- -----------------------------------------------------------------------------
-- 初始化默认模拟盘账户
-- -----------------------------------------------------------------------------

SELECT '初始化默认模拟盘账户...' AS '初始化步骤';

INSERT IGNORE INTO `sim_account` (`account_name`, `initial_capital`, `current_capital`, `market_value`, `total_asset`, `description`)
VALUES ('默认模拟账户', 1000000.00, 1000000.00, 0.00, 1000000.00, '系统默认模拟盘账户，初始资金100万元');

SELECT '====================================' AS '';
SELECT '数据库迁移 V005 执行完成' AS '完成状态';
SELECT '完成时间:' AS '', NOW() AS '';
SELECT '====================================' AS '';
