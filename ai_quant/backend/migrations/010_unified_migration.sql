-- =============================================================================
-- AI 量化交易系统 - 数据库统一迁移脚本
-- 版本: 010
-- 创建日期: 2026-05-16
-- 描述: 将所有新增功能的表结构统一迁移到腾讯云MySQL
--       包含: 信号中心、绩效报告、模拟盘、风控看板、主力识别、审批流程、基本面选股扩展
-- 注意: 使用 trade_ 前缀保持命名一致性，使用 IF NOT EXISTS 保证幂等性
-- =============================================================================

-- ============================================
-- 第一部分: 信号中心
-- ============================================

-- 1. 信号规则表
CREATE TABLE IF NOT EXISTS `trade_signal_rule` (
    `id` VARCHAR(64) NOT NULL COMMENT '规则ID',
    `name` VARCHAR(255) NOT NULL COMMENT '规则名称',
    `description` TEXT COMMENT '规则描述',
    `logic_type` ENUM('AND', 'OR') NOT NULL DEFAULT 'AND' COMMENT '条件逻辑: AND/OR',
    `enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用: 0-禁用 1-启用',
    `priority` INT NOT NULL DEFAULT 0 COMMENT '优先级',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_signal_rule_enabled` (`enabled`),
    KEY `idx_signal_rule_priority` (`priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='信号规则表';

-- 2. 信号规则条件表
CREATE TABLE IF NOT EXISTS `trade_signal_rule_condition` (
    `id` VARCHAR(64) NOT NULL COMMENT '条件ID',
    `rule_id` VARCHAR(64) NOT NULL COMMENT '关联规则ID',
    `indicator` VARCHAR(64) NOT NULL COMMENT '指标名称',
    `operator` VARCHAR(32) NOT NULL COMMENT '操作符: gt/lt/gte/lte/eq/cross_up/cross_down',
    `threshold_value` DECIMAL(20, 4) NOT NULL DEFAULT 0 COMMENT '阈值',
    `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序顺序',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_signal_cond_rule` (`rule_id`),
    CONSTRAINT `fk_signal_cond_rule` FOREIGN KEY (`rule_id`) REFERENCES `trade_signal_rule`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='信号规则条件表';

-- 3. 信号记录表
CREATE TABLE IF NOT EXISTS `trade_signal_record` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `signal_id` VARCHAR(64) NOT NULL COMMENT '信号ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) DEFAULT '' COMMENT '股票名称',
    `signal_type` ENUM('BUY', 'SELL') NOT NULL COMMENT '信号类型: BUY/SELL',
    `strength` INT NOT NULL DEFAULT 3 COMMENT '信号强度 1-5',
    `score` DECIMAL(10, 2) NOT NULL DEFAULT 0 COMMENT '信号评分 0-100',
    `close_price` DECIMAL(20, 4) NOT NULL COMMENT '收盘价',
    `reason` TEXT COMMENT '信号原因',
    `rule_id` VARCHAR(64) COMMENT '触发规则ID',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态: pending/triggered/expired/cancelled',
    `macd` DECIMAL(20, 6) DEFAULT NULL COMMENT 'MACD值',
    `rsi` DECIMAL(10, 2) DEFAULT NULL COMMENT 'RSI值',
    `ma5` DECIMAL(20, 4) DEFAULT NULL COMMENT 'MA5值',
    `ma10` DECIMAL(20, 4) DEFAULT NULL COMMENT 'MA10值',
    `ma20` DECIMAL(20, 4) DEFAULT NULL COMMENT 'MA20值',
    `ma60` DECIMAL(20, 4) DEFAULT NULL COMMENT 'MA60值',
    `boll_upper` DECIMAL(20, 4) DEFAULT NULL COMMENT '布林上轨',
    `boll_mid` DECIMAL(20, 4) DEFAULT NULL COMMENT '布林中轨',
    `boll_lower` DECIMAL(20, 4) DEFAULT NULL COMMENT '布林下轨',
    `trade_date` DATE NOT NULL COMMENT '交易日期',
    `expired_at` DATETIME DEFAULT NULL COMMENT '过期时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_signal_id` (`signal_id`),
    KEY `idx_signal_record_code` (`stock_code`),
    KEY `idx_signal_record_type` (`signal_type`),
    KEY `idx_signal_record_strength` (`strength`),
    KEY `idx_signal_record_status` (`status`),
    KEY `idx_signal_record_date` (`trade_date`),
    KEY `idx_signal_record_created` (`created_at`),
    KEY `idx_signal_record_composite` (`trade_date`, `signal_type`, `strength`),
    CONSTRAINT `fk_signal_record_rule` FOREIGN KEY (`rule_id`) REFERENCES `trade_signal_rule`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='信号记录表';

-- 4. 信号历史快照表
CREATE TABLE IF NOT EXISTS `trade_signal_snapshot` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `signal_id` VARCHAR(64) NOT NULL COMMENT '关联信号ID',
    `snapshot_data` JSON COMMENT '技术指标快照JSON',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_signal_snapshot_sid` (`signal_id`),
    CONSTRAINT `fk_signal_snapshot_signal` FOREIGN KEY (`signal_id`) REFERENCES `trade_signal_record`(`signal_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='信号历史快照表';

-- 5. 信号统计表
CREATE TABLE IF NOT EXISTS `trade_signal_statistic` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stat_date` DATE NOT NULL COMMENT '统计日期',
    `stat_type` ENUM('DAILY', 'WEEKLY', 'MONTHLY') NOT NULL COMMENT '统计类型',
    `buy_count` INT NOT NULL DEFAULT 0 COMMENT '买入信号数量',
    `sell_count` INT NOT NULL DEFAULT 0 COMMENT '卖出信号数量',
    `avg_strength` DECIMAL(5, 2) NOT NULL DEFAULT 0 COMMENT '平均信号强度',
    `top_stocks` JSON COMMENT '热门股票JSON',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_stat_date_type` (`stat_date`, `stat_type`),
    KEY `idx_signal_stat_date` (`stat_date`),
    KEY `idx_signal_stat_type` (`stat_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='信号统计表';

-- ============================================
-- 第二部分: 绩效报告
-- ============================================

-- 6. 绩效报告表
CREATE TABLE IF NOT EXISTS `trade_performance_report` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `report_id` VARCHAR(64) NOT NULL COMMENT '报告ID',
    `report_type` VARCHAR(20) NOT NULL COMMENT '报告类型: common/plus',
    `account_id` INT DEFAULT NULL COMMENT '关联账户ID',
    `strategy_name` VARCHAR(100) DEFAULT NULL COMMENT '策略名称',
    `strategy_params` TEXT COMMENT '策略参数JSON',
    `backtest_id` VARCHAR(64) DEFAULT NULL COMMENT '关联的回测ID',
    `start_date` DATE NOT NULL COMMENT '开始日期',
    `end_date` DATE NOT NULL COMMENT '结束日期',
    `initial_cash` DECIMAL(15, 2) NOT NULL COMMENT '初始资金',
    `final_nav` DECIMAL(15, 4) NOT NULL DEFAULT 1.0000 COMMENT '最终净值',
    `benchmark_code` VARCHAR(20) DEFAULT NULL COMMENT '基准代码',
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
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态: pending/completed/failed',
    `error_message` TEXT COMMENT '错误信息',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_report_id` (`report_id`),
    KEY `idx_perf_report_type` (`report_type`),
    KEY `idx_perf_report_status` (`status`),
    KEY `idx_perf_report_account` (`account_id`),
    KEY `idx_perf_report_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='绩效报告表';

-- 7. 回测记录表
CREATE TABLE IF NOT EXISTS `trade_backtest_record` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
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
    `status` VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT '状态: running/completed/failed',
    `error_message` TEXT COMMENT '错误信息',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_backtest_id` (`backtest_id`),
    KEY `idx_backtest_strategy` (`strategy_name`),
    KEY `idx_backtest_stock` (`stock_code`),
    KEY `idx_backtest_status` (`status`),
    KEY `idx_backtest_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='回测记录表';

-- ============================================
-- 第三部分: 模拟盘
-- ============================================

-- 8. 模拟账户表
CREATE TABLE IF NOT EXISTS `trade_sim_account` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `account_name` VARCHAR(100) NOT NULL COMMENT '账户名称',
    `initial_capital` DECIMAL(15, 2) NOT NULL COMMENT '初始资金',
    `current_capital` DECIMAL(15, 2) NOT NULL COMMENT '当前可用资金',
    `frozen_capital` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '冻结资金',
    `market_value` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '持仓市值',
    `total_asset` DECIMAL(15, 2) NOT NULL COMMENT '总资产',
    `total_pnl` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '总盈亏',
    `total_pnl_pct` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000 COMMENT '总盈亏比例(%)',
    `today_pnl` DECIMAL(15, 2) NOT NULL DEFAULT 0.00 COMMENT '今日盈亏',
    `today_pnl_pct` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000 COMMENT '今日盈亏比例(%)',
    `position_count` INT NOT NULL DEFAULT 0 COMMENT '持仓数量',
    `leverage_ratio` DECIMAL(10, 4) DEFAULT 1.0 COMMENT '杠杆率',
    `liquidity_ratio` DECIMAL(10, 4) DEFAULT 2.0 COMMENT '流动性比率',
    `risk_score` DECIMAL(10, 2) DEFAULT 0 COMMENT '风险评分(0-100)',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low' COMMENT '风险等级',
    `concentration_ratio` DECIMAL(10, 4) DEFAULT NULL COMMENT '集中度',
    `margin_ratio` DECIMAL(10, 4) DEFAULT NULL COMMENT '保证金比例',
    `max_drawdown` DECIMAL(10, 4) DEFAULT NULL COMMENT '历史最大回撤(%)',
    `win_rate` DECIMAL(6, 2) DEFAULT NULL COMMENT '历史胜率(%)',
    `total_trades` INT NOT NULL DEFAULT 0 COMMENT '历史总交易次数',
    `winning_trades` INT NOT NULL DEFAULT 0 COMMENT '盈利交易次数',
    `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '状态: active/closed',
    `description` TEXT COMMENT '账户描述',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_sim_account_name` (`account_name`),
    KEY `idx_sim_account_status` (`status`),
    KEY `idx_sim_account_risk` (`risk_level`),
    KEY `idx_sim_account_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模拟账户表';

-- 9. 模拟账户持仓表
CREATE TABLE IF NOT EXISTS `trade_sim_position` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `account_id` INT NOT NULL COMMENT '账户ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
    `volume` INT NOT NULL COMMENT '持仓数量',
    `available_volume` INT NOT NULL COMMENT '可用数量',
    `cost` DECIMAL(15, 4) NOT NULL COMMENT '成本价',
    `cur_price` DECIMAL(15, 4) NOT NULL COMMENT '当前价格',
    `market_value` DECIMAL(15, 2) NOT NULL COMMENT '市值',
    `pnl` DECIMAL(15, 2) NOT NULL COMMENT '盈亏金额',
    `pnl_pct` DECIMAL(10, 4) NOT NULL COMMENT '盈亏比例(%)',
    `risk_value` DECIMAL(10, 2) DEFAULT 0 COMMENT '风险值(0-100)',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low' COMMENT '风险等级',
    `var_95` DECIMAL(20, 4) DEFAULT NULL COMMENT 'VaR 95%置信度',
    `volatility` DECIMAL(10, 4) DEFAULT NULL COMMENT '波动率',
    `beta` DECIMAL(10, 4) DEFAULT NULL COMMENT 'Beta值',
    `max_loss_rate` DECIMAL(10, 4) DEFAULT NULL COMMENT '最大亏损率',
    `stop_loss_price` DECIMAL(20, 4) DEFAULT NULL COMMENT '止损价',
    `target_price` DECIMAL(20, 4) DEFAULT NULL COMMENT '目标价',
    `position_type` VARCHAR(20) NOT NULL DEFAULT 'normal' COMMENT '持仓类型: normal/locked',
    `buy_date` DATE DEFAULT NULL COMMENT '买入日期',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_sim_pos_account_stock` (`account_id`, `stock_code`),
    KEY `idx_sim_pos_account` (`account_id`),
    KEY `idx_sim_pos_stock` (`stock_code`),
    KEY `idx_sim_pos_risk` (`risk_level`),
    KEY `idx_sim_pos_created` (`created_at`),
    CONSTRAINT `fk_sim_pos_account` FOREIGN KEY (`account_id`) REFERENCES `trade_sim_account`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模拟账户持仓表';

-- 10. 模拟账户交易记录表
CREATE TABLE IF NOT EXISTS `trade_sim_trade` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `trade_no` VARCHAR(64) NOT NULL COMMENT '交易编号',
    `account_id` INT NOT NULL COMMENT '账户ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
    `side` VARCHAR(10) NOT NULL COMMENT '买卖方向: buy/sell',
    `price` DECIMAL(15, 4) NOT NULL COMMENT '成交价格',
    `volume` INT NOT NULL COMMENT '成交数量',
    `amount` DECIMAL(15, 2) NOT NULL COMMENT '成交金额',
    `commission` DECIMAL(10, 2) NOT NULL DEFAULT 0.00 COMMENT '手续费',
    `account_type` VARCHAR(20) NOT NULL DEFAULT 'sim' COMMENT '账户类型: sim/real',
    `trade_time` DATETIME NOT NULL COMMENT '成交时间',
    `strategy` VARCHAR(100) DEFAULT NULL COMMENT '策略名称',
    `signal_source` VARCHAR(50) DEFAULT NULL COMMENT '信号来源',
    `remark` TEXT COMMENT '备注',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_trade_no` (`trade_no`),
    KEY `idx_sim_trade_account` (`account_id`),
    KEY `idx_sim_trade_stock` (`stock_code`),
    KEY `idx_sim_trade_time` (`trade_time`),
    KEY `idx_sim_trade_side` (`side`),
    CONSTRAINT `fk_sim_trade_account` FOREIGN KEY (`account_id`) REFERENCES `trade_sim_account`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模拟账户交易记录表';

-- ============================================
-- 第四部分: 风控看板
-- ============================================

-- 11. 风险事件表
CREATE TABLE IF NOT EXISTS `trade_risk_event` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `event_id` VARCHAR(64) NOT NULL COMMENT '事件ID',
    `event_type` VARCHAR(30) NOT NULL COMMENT '事件类型: stop_loss/position_overflow/liquidity/mainforce_activity/price_alert/volatility',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') NOT NULL COMMENT '风险等级',
    `stock_code` VARCHAR(20) DEFAULT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) DEFAULT NULL COMMENT '股票名称',
    `position_id` INT DEFAULT NULL COMMENT '持仓记录ID',
    `account_id` VARCHAR(32) NOT NULL COMMENT '账户ID',
    `description` TEXT COMMENT '事件描述',
    `event_data` JSON COMMENT '事件详情(JSON)',
    `triggered_rule_id` BIGINT DEFAULT NULL COMMENT '触发的规则ID',
    `status` ENUM('pending', 'confirmed', 'ignored', 'processed', 'expired') NOT NULL DEFAULT 'pending' COMMENT '处理状态',
    `handler_id` VARCHAR(64) DEFAULT NULL COMMENT '处理人ID',
    `handle_comment` TEXT COMMENT '处理意见',
    `handled_at` DATETIME DEFAULT NULL COMMENT '处理时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_risk_event_id` (`event_id`),
    KEY `idx_risk_event_type` (`event_type`),
    KEY `idx_risk_event_level` (`risk_level`),
    KEY `idx_risk_event_status` (`status`),
    KEY `idx_risk_event_stock` (`stock_code`),
    KEY `idx_risk_event_account` (`account_id`),
    KEY `idx_risk_event_created` (`created_at`),
    KEY `idx_risk_event_rule` (`triggered_rule_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风险事件表';

-- 12. 风控告警表
CREATE TABLE IF NOT EXISTS `trade_risk_alert` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `alert_id` VARCHAR(64) NOT NULL COMMENT '告警ID',
    `alert_type` VARCHAR(30) NOT NULL COMMENT '告警类型: stop_loss/position_overflow/liquidity/mainforce_activity/price_alert/volatility/system',
    `level` ENUM('red', 'orange', 'yellow', 'green') NOT NULL COMMENT '告警级别: red-紧急 orange-重要 yellow-一般 green-正常',
    `stock_code` VARCHAR(20) DEFAULT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) DEFAULT NULL COMMENT '股票名称',
    `account_id` VARCHAR(32) NOT NULL COMMENT '账户ID',
    `message` TEXT NOT NULL COMMENT '告警消息',
    `metric_value` DECIMAL(20, 4) DEFAULT NULL COMMENT '触发时的指标值',
    `threshold_value` DECIMAL(20, 4) DEFAULT NULL COMMENT '阈值',
    `status` ENUM('pending', 'confirmed', 'ignored', 'processed') NOT NULL DEFAULT 'pending' COMMENT '处理状态',
    `handler_id` VARCHAR(64) DEFAULT NULL COMMENT '处理人ID',
    `handle_result` TEXT COMMENT '处理结果',
    `handled_at` DATETIME DEFAULT NULL COMMENT '处理时间',
    `is_read` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已读',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_risk_alert_id` (`alert_id`),
    KEY `idx_risk_alert_type` (`alert_type`),
    KEY `idx_risk_alert_level` (`level`),
    KEY `idx_risk_alert_status` (`status`),
    KEY `idx_risk_alert_stock` (`stock_code`),
    KEY `idx_risk_alert_account` (`account_id`),
    KEY `idx_risk_alert_created` (`created_at`),
    KEY `idx_risk_alert_read` (`is_read`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风控告警表';

-- 13. 风控操作日志表
CREATE TABLE IF NOT EXISTS `trade_risk_operation_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `operator_id` VARCHAR(64) NOT NULL COMMENT '操作人ID',
    `operator_name` VARCHAR(100) DEFAULT NULL COMMENT '操作人姓名',
    `operation_type` VARCHAR(30) NOT NULL COMMENT '操作类型: create_rule/update_rule/delete_rule/handle_alert/confirm_alert/ignore_alert/process_alert/modify_threshold',
    `target_type` VARCHAR(20) NOT NULL COMMENT '操作对象类型: rule/alert/event/account',
    `target_id` VARCHAR(64) NOT NULL COMMENT '操作对象ID',
    `target_name` VARCHAR(255) DEFAULT NULL COMMENT '操作对象名称',
    `old_value` JSON COMMENT '修改前的值',
    `new_value` JSON COMMENT '修改后的值',
    `ip_address` VARCHAR(50) DEFAULT NULL COMMENT 'IP地址',
    `user_agent` VARCHAR(500) DEFAULT NULL COMMENT 'User-Agent',
    `result` ENUM('success', 'failed') NOT NULL COMMENT '操作结果',
    `error_message` TEXT COMMENT '错误信息',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_risk_oplog_operator` (`operator_id`),
    KEY `idx_risk_oplog_type` (`operation_type`),
    KEY `idx_risk_oplog_target` (`target_type`, `target_id`),
    KEY `idx_risk_oplog_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风控操作日志表';

-- 14. 持仓风险表
CREATE TABLE IF NOT EXISTS `trade_position_risk` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `account_id` VARCHAR(32) NOT NULL COMMENT '账户ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
    `position_value` DECIMAL(20, 2) NOT NULL COMMENT '持仓市值',
    `position_ratio` DECIMAL(10, 4) NOT NULL COMMENT '持仓占比',
    `risk_value` DECIMAL(10, 2) NOT NULL COMMENT '风险值(0-100)',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') NOT NULL COMMENT '风险等级',
    `var_95` DECIMAL(20, 4) DEFAULT NULL COMMENT 'VaR 95%置信度',
    `volatility` DECIMAL(10, 4) DEFAULT NULL COMMENT '波动率',
    `beta` DECIMAL(10, 4) DEFAULT NULL COMMENT 'Beta值',
    `max_loss_rate` DECIMAL(10, 4) DEFAULT NULL COMMENT '最大亏损率',
    `stop_loss_price` DECIMAL(20, 4) DEFAULT NULL COMMENT '止损价',
    `position_date` DATE NOT NULL COMMENT '持仓日期',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_pos_risk_account_stock_date` (`account_id`, `stock_code`, `position_date`),
    KEY `idx_pos_risk_account` (`account_id`),
    KEY `idx_pos_risk_level` (`risk_level`),
    KEY `idx_pos_risk_value` (`risk_value`),
    KEY `idx_pos_risk_date` (`position_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='持仓风险表';

-- 15. 账户风险指标表
CREATE TABLE IF NOT EXISTS `trade_account_risk_metric` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `account_id` VARCHAR(32) NOT NULL COMMENT '账户ID',
    `total_value` DECIMAL(20, 2) NOT NULL COMMENT '总资产',
    `cash_balance` DECIMAL(20, 2) NOT NULL COMMENT '现金余额',
    `position_value` DECIMAL(20, 2) NOT NULL COMMENT '持仓市值',
    `liability_value` DECIMAL(20, 2) NOT NULL DEFAULT 0 COMMENT '负债值',
    `leverage_ratio` DECIMAL(10, 4) NOT NULL COMMENT '杠杆率',
    `liquidity_ratio` DECIMAL(10, 4) NOT NULL COMMENT '流动性比率',
    `risk_score` DECIMAL(10, 2) NOT NULL COMMENT '风险评分(0-100)',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') NOT NULL COMMENT '风险等级',
    `margin_ratio` DECIMAL(10, 4) DEFAULT NULL COMMENT '保证金比例',
    `concentration_ratio` DECIMAL(10, 4) DEFAULT NULL COMMENT '集中度',
    `net_value` DECIMAL(20, 4) DEFAULT NULL COMMENT '净值',
    `daily_return` DECIMAL(10, 4) DEFAULT NULL COMMENT '日收益率',
    `max_drawdown` DECIMAL(10, 4) DEFAULT NULL COMMENT '最大回撤',
    `record_date` DATE NOT NULL COMMENT '记录日期',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_account_risk_date` (`account_id`, `record_date`),
    KEY `idx_account_risk_account` (`account_id`),
    KEY `idx_account_risk_score` (`risk_score`),
    KEY `idx_account_risk_level` (`risk_level`),
    KEY `idx_account_risk_date` (`record_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账户风险指标表';

-- ============================================
-- 第五部分: 主力识别
-- ============================================

-- 16. 主力活动记录表
CREATE TABLE IF NOT EXISTS `trade_mainforce_activity` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `activity_date` DATE NOT NULL COMMENT '活动日期',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
    `activity_type` ENUM('BUY', 'SELL') NOT NULL COMMENT '活动类型: BUY/SELL',
    `volume` BIGINT NOT NULL COMMENT '成交量(股)',
    `amount` DECIMAL(20, 2) NOT NULL COMMENT '成交金额(元)',
    `price` DECIMAL(20, 4) NOT NULL COMMENT '成交价格',
    `ratio` DECIMAL(10, 4) NOT NULL COMMENT '大单占比(0-1)',
    `mainforce_type` ENUM('institution', 'hot_money', 'retail') NOT NULL DEFAULT 'retail' COMMENT '主力类型: institution/hot_money/retail',
    `description` TEXT COMMENT '活动描述',
    `indicators` JSON COMMENT '识别指标详情(JSON)',
    `is_anomaly` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否异常: 0-正常 1-异常',
    `alert_status` ENUM('none', 'pending', 'triggered') NOT NULL DEFAULT 'none' COMMENT '告警状态',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_mf_activity_date` (`activity_date`),
    KEY `idx_mf_activity_stock` (`stock_code`),
    KEY `idx_mf_activity_type` (`activity_type`),
    KEY `idx_mf_activity_mftype` (`mainforce_type`),
    KEY `idx_mf_activity_anomaly` (`is_anomaly`),
    KEY `idx_mf_activity_alert` (`alert_status`),
    KEY `idx_mf_activity_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力活动记录表';

-- 17. 主力识别任务表
CREATE TABLE IF NOT EXISTS `trade_mainforce_task` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `task_id` VARCHAR(64) NOT NULL COMMENT '任务ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `company_name` VARCHAR(100) DEFAULT NULL COMMENT '公司名称',
    `mode` ENUM('simulated', 'realtime') NOT NULL DEFAULT 'simulated' COMMENT '识别模式: simulated/realtime',
    `params` JSON NOT NULL COMMENT '任务参数(JSON)',
    `status` ENUM('pending', 'running', 'done', 'failed') NOT NULL DEFAULT 'pending' COMMENT '任务状态',
    `result` JSON COMMENT '运行结果(JSON)',
    `error_message` TEXT COMMENT '错误信息',
    `triggered_rule_id` BIGINT DEFAULT NULL COMMENT '触发的告警规则ID',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_mf_task_id` (`task_id`),
    KEY `idx_mf_task_stock` (`stock_code`),
    KEY `idx_mf_task_status` (`status`),
    KEY `idx_mf_task_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力识别任务表';

-- 18. 主力持仓变化表
CREATE TABLE IF NOT EXISTS `trade_mainforce_position_change` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
    `position_date` DATE NOT NULL COMMENT '持仓日期',
    `position_ratio` DECIMAL(10, 4) NOT NULL COMMENT '持仓比例(0-1)',
    `position_change` DECIMAL(10, 4) NOT NULL COMMENT '持仓比例变化',
    `position_value` DECIMAL(20, 2) DEFAULT NULL COMMENT '持仓市值(元)',
    `change_type` ENUM('increase', 'decrease', 'stable') NOT NULL COMMENT '变化类型',
    `reason` TEXT COMMENT '变化原因',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_mf_pos_stock_date` (`stock_code`, `position_date`),
    KEY `idx_mf_pos_stock` (`stock_code`),
    KEY `idx_mf_pos_date` (`position_date`),
    KEY `idx_mf_pos_change` (`change_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力持仓变化表';

-- 19. K线标注表
CREATE TABLE IF NOT EXISTS `trade_kline_marker` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
    `marker_date` DATE NOT NULL COMMENT '标注日期',
    `marker_price` DECIMAL(20, 4) NOT NULL COMMENT '标注价格',
    `marker_type` ENUM('BUY', 'SELL') NOT NULL COMMENT '标注类型: BUY/SELL',
    `volume` BIGINT DEFAULT NULL COMMENT '成交量(股)',
    `amount` DECIMAL(20, 2) DEFAULT NULL COMMENT '成交金额(元)',
    `mainforce_type` ENUM('institution', 'hot_money', 'retail') NOT NULL DEFAULT 'retail' COMMENT '主力类型',
    `source` ENUM('auto', 'manual') NOT NULL DEFAULT 'auto' COMMENT '标注来源: auto/manual',
    `activity_id` BIGINT DEFAULT NULL COMMENT '关联的主力活动ID',
    `description` TEXT COMMENT '标注描述',
    `is_visible` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否显示: 0-隐藏 1-显示',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_kline_marker` (`stock_code`, `marker_date`, `marker_type`),
    KEY `idx_kline_marker_stock` (`stock_code`),
    KEY `idx_kline_marker_date` (`marker_date`),
    KEY `idx_kline_marker_type` (`marker_type`),
    KEY `idx_kline_marker_source` (`source`),
    KEY `idx_kline_marker_visible` (`is_visible`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='K线标注表';

-- 20. 主力告警规则表
CREATE TABLE IF NOT EXISTS `trade_mainforce_alert_rule` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `name` VARCHAR(100) NOT NULL COMMENT '规则名称',
    `rule_type` VARCHAR(30) NOT NULL COMMENT '规则类型: volume_anomaly/large_order/netflow/position_change',
    `description` TEXT COMMENT '规则描述',
    `enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用: 0-禁用 1-启用',
    `threshold` DECIMAL(20, 4) NOT NULL COMMENT '阈值',
    `threshold_unit` VARCHAR(20) DEFAULT NULL COMMENT '阈值单位: times/yuan/percent',
    `condition` JSON COMMENT '触发条件(JSON)',
    `action` ENUM('alert', 'block', 'auto_close') NOT NULL DEFAULT 'alert' COMMENT '触发动作',
    `priority` INT NOT NULL DEFAULT 0 COMMENT '优先级',
    `trigger_count` INT NOT NULL DEFAULT 0 COMMENT '累计触发次数',
    `last_trigger_time` DATETIME DEFAULT NULL COMMENT '最后触发时间',
    `last_trigger_value` DECIMAL(20, 4) DEFAULT NULL COMMENT '最后触发时的值',
    `alert_template` TEXT COMMENT '告警消息模板',
    `created_by` VARCHAR(64) DEFAULT NULL COMMENT '创建人',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_mf_rule_type` (`rule_type`),
    KEY `idx_mf_rule_enabled` (`enabled`),
    KEY `idx_mf_rule_priority` (`priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力告警规则表';

-- 21. 主力识别统计表
CREATE TABLE IF NOT EXISTS `trade_mainforce_statistic` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stat_date` DATE NOT NULL COMMENT '统计日期',
    `buy_count` INT NOT NULL DEFAULT 0 COMMENT '买入次数',
    `sell_count` INT NOT NULL DEFAULT 0 COMMENT '卖出次数',
    `total_buy_amount` DECIMAL(20, 2) NOT NULL DEFAULT 0 COMMENT '总买入金额(元)',
    `total_sell_amount` DECIMAL(20, 2) NOT NULL DEFAULT 0 COMMENT '总卖出金额(元)',
    `net_flow` DECIMAL(20, 2) NOT NULL DEFAULT 0 COMMENT '净流入(元)',
    `institution_buy_count` INT NOT NULL DEFAULT 0 COMMENT '机构买入次数',
    `hot_money_buy_count` INT NOT NULL DEFAULT 0 COMMENT '游资买入次数',
    `retail_sell_count` INT NOT NULL DEFAULT 0 COMMENT '散户卖出次数',
    `anomaly_count` INT NOT NULL DEFAULT 0 COMMENT '异常活动次数',
    `alert_count` INT NOT NULL DEFAULT 0 COMMENT '触发告警次数',
    `top_stocks` JSON COMMENT '活跃股票列表(JSON)',
    `summary` TEXT COMMENT '统计摘要',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_mf_stat_date` (`stat_date`),
    KEY `idx_mf_stat_date` (`stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力识别统计表';

-- 22. 主力资金流表
CREATE TABLE IF NOT EXISTS `trade_mainforce_flow` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(100) NOT NULL COMMENT '股票名称',
    `trade_date` DATE NOT NULL COMMENT '交易日期',
    `main_inflow` DECIMAL(20, 2) DEFAULT NULL COMMENT '主力净流入(元)',
    `main_outflow` DECIMAL(20, 2) DEFAULT NULL COMMENT '主力净流出(元)',
    `main_netflow` DECIMAL(20, 2) DEFAULT NULL COMMENT '主力净流入净额(元)',
    `main_inflow_ratio` DECIMAL(10, 4) DEFAULT NULL COMMENT '主力净流入占比',
    `retail_inflow` DECIMAL(20, 2) DEFAULT NULL COMMENT '散户净流入',
    `total_volume` DECIMAL(20, 2) DEFAULT NULL COMMENT '总成交量',
    `close_price` DECIMAL(20, 4) DEFAULT NULL COMMENT '收盘价',
    `price_change` DECIMAL(10, 4) DEFAULT NULL COMMENT '涨跌幅',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_mf_flow_stock_date` (`stock_code`, `trade_date`),
    KEY `idx_mf_flow_stock` (`stock_code`),
    KEY `idx_mf_flow_date` (`trade_date`),
    KEY `idx_mf_flow_netflow` (`main_netflow`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力资金流表';

-- ============================================
-- 第六部分: 审批流程
-- ============================================

-- 23. 审批流程模板表
CREATE TABLE IF NOT EXISTS `trade_approval_template` (
    `id` VARCHAR(64) NOT NULL COMMENT '模板ID',
    `name` VARCHAR(255) NOT NULL COMMENT '模板名称',
    `description` TEXT COMMENT '模板描述',
    `status` ENUM('draft', 'active', 'archived') NOT NULL DEFAULT 'draft' COMMENT '状态: draft/active/archived',
    `nodes` JSON NOT NULL COMMENT '节点定义(JSON)',
    `edges` JSON NOT NULL COMMENT '边定义(JSON)',
    `created_by` VARCHAR(64) DEFAULT NULL COMMENT '创建人',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_approval_tpl_status` (`status`),
    KEY `idx_approval_tpl_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审批流程模板表';

-- 24. 审批流程实例表
CREATE TABLE IF NOT EXISTS `trade_approval_instance` (
    `id` VARCHAR(64) NOT NULL COMMENT '实例ID',
    `template_id` VARCHAR(64) NOT NULL COMMENT '模板ID',
    `template_name` VARCHAR(255) NOT NULL COMMENT '模板名称',
    `title` VARCHAR(255) NOT NULL COMMENT '审批标题',
    `applicant_id` VARCHAR(64) NOT NULL COMMENT '申请人ID',
    `applicant_name` VARCHAR(100) DEFAULT NULL COMMENT '申请人姓名',
    `status` ENUM('pending', 'processing', 'approved', 'rejected', 'returned', 'cancelled') NOT NULL DEFAULT 'pending' COMMENT '状态',
    `form_data` JSON COMMENT '表单数据(JSON)',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_approval_inst_tpl` (`template_id`),
    KEY `idx_approval_inst_status` (`status`),
    KEY `idx_approval_inst_applicant` (`applicant_id`),
    KEY `idx_approval_inst_created` (`created_at`),
    CONSTRAINT `fk_approval_inst_tpl` FOREIGN KEY (`template_id`) REFERENCES `trade_approval_template`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审批流程实例表';

-- 25. 审批节点实例表
CREATE TABLE IF NOT EXISTS `trade_approval_node_instance` (
    `id` VARCHAR(64) NOT NULL COMMENT '节点实例ID',
    `instance_id` VARCHAR(64) NOT NULL COMMENT '流程实例ID',
    `node_id` VARCHAR(64) NOT NULL COMMENT '模板节点ID',
    `node_label` VARCHAR(255) NOT NULL COMMENT '节点名称',
    `node_type` ENUM('start', 'end', 'approver', 'condition', 'notify') NOT NULL COMMENT '节点类型',
    `assignee_type` VARCHAR(20) DEFAULT NULL COMMENT '审批人类型: role/user/department',
    `assignee_id` VARCHAR(64) DEFAULT NULL COMMENT '审批人ID',
    `assignee_name` VARCHAR(100) DEFAULT NULL COMMENT '审批人姓名',
    `status` ENUM('pending', 'approved', 'rejected', 'returned', 'skipped') NOT NULL DEFAULT 'pending' COMMENT '状态',
    `completed_at` DATETIME DEFAULT NULL COMMENT '完成时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_approval_node_inst` (`instance_id`),
    KEY `idx_approval_node_status` (`status`),
    KEY `idx_approval_node_assignee` (`assignee_id`),
    CONSTRAINT `fk_approval_node_inst` FOREIGN KEY (`instance_id`) REFERENCES `trade_approval_instance`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审批节点实例表';

-- 26. 审批记录表
CREATE TABLE IF NOT EXISTS `trade_approval_record` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `record_id` VARCHAR(64) NOT NULL COMMENT '记录ID',
    `instance_id` VARCHAR(64) NOT NULL COMMENT '流程实例ID',
    `node_instance_id` VARCHAR(64) NOT NULL COMMENT '节点实例ID',
    `node_label` VARCHAR(255) DEFAULT NULL COMMENT '节点名称',
    `approver_id` VARCHAR(64) NOT NULL COMMENT '审批人ID',
    `approver_name` VARCHAR(100) DEFAULT NULL COMMENT '审批人姓名',
    `action` ENUM('approve', 'reject', 'return') NOT NULL COMMENT '审批动作',
    `comment` TEXT COMMENT '审批意见',
    `attachment_url` VARCHAR(500) DEFAULT NULL COMMENT '附件URL',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_approval_record_id` (`record_id`),
    KEY `idx_approval_record_inst` (`instance_id`),
    KEY `idx_approval_record_node` (`node_instance_id`),
    KEY `idx_approval_record_approver` (`approver_id`),
    KEY `idx_approval_record_created` (`created_at`),
    CONSTRAINT `fk_approval_record_inst` FOREIGN KEY (`instance_id`) REFERENCES `trade_approval_instance`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审批记录表';

-- ============================================
-- 第七部分: 扩展现有表
-- ============================================

-- 27. 扩展 trade_risk_rule 表 - 添加触发统计字段
-- 使用存储过程安全添加列（如果列不存在则添加）
DROP PROCEDURE IF EXISTS `add_column_if_not_exists`;
DELIMITER $$
CREATE PROCEDURE `add_column_if_not_exists`(
    IN `p_table` VARCHAR(64),
    IN `p_column` VARCHAR(64),
    IN `p_definition` VARCHAR(500)
)
BEGIN
    DECLARE `col_exists` INT DEFAULT 0;
    SELECT COUNT(*) INTO `col_exists`
    FROM `information_schema`.`columns`
    WHERE `table_schema` = DATABASE()
      AND `table_name` = `p_table`
      AND `column_name` = `p_column`;
    IF `col_exists` = 0 THEN
        SET @sql = CONCAT('ALTER TABLE `', `p_table`, '` ADD COLUMN `', `p_column`, '` ', `p_definition`);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$
DELIMITER ;

-- 扩展 trade_risk_rule
CALL `add_column_if_not_exists`('trade_risk_rule', 'trigger_count', 'INT NOT NULL DEFAULT 0 COMMENT "累计触发次数" AFTER `notes`');
CALL `add_column_if_not_exists`('trade_risk_rule', 'last_trigger_time', 'DATETIME DEFAULT NULL COMMENT "最后触发时间" AFTER `trigger_count`');
CALL `add_column_if_not_exists`('trade_risk_rule', 'last_trigger_value', 'VARCHAR(100) DEFAULT NULL COMMENT "最后触发时的值" AFTER `last_trigger_time`');
CALL `add_column_if_not_exists`('trade_risk_rule', 'status', 'ENUM("active", "inactive", "triggered") NOT NULL DEFAULT "active" COMMENT "规则状态" AFTER `last_trigger_value`');
CALL `add_column_if_not_exists`('trade_risk_rule', 'created_by', 'VARCHAR(64) DEFAULT NULL COMMENT "创建人" AFTER `status`');

-- 扩展 trade_stock_financial - 添加更多财务指标（优化基本面选股）
CALL `add_column_if_not_exists`('trade_stock_financial', 'operating_margin', 'DECIMAL(10,4) DEFAULT NULL COMMENT "营业利润率(%)" AFTER `psr`');
CALL `add_column_if_not_exists`('trade_stock_financial', 'quick_ratio', 'DECIMAL(10,4) DEFAULT NULL COMMENT "速动比率" AFTER `operating_margin`');
CALL `add_column_if_not_exists`('trade_stock_financial', 'total_asset_turnover', 'DECIMAL(10,4) DEFAULT NULL COMMENT "总资产周转率" AFTER `quick_ratio`');
CALL `add_column_if_not_exists`('trade_stock_financial', 'inventory_turnover', 'DECIMAL(10,4) DEFAULT NULL COMMENT "存货周转率" AFTER `total_asset_turnover`');
CALL `add_column_if_not_exists`('trade_stock_financial', 'receivables_turnover', 'DECIMAL(10,4) DEFAULT NULL COMMENT "应收账款周转率" AFTER `inventory_turnover`');
CALL `add_column_if_not_exists`('trade_stock_financial', 'free_cash_flow', 'DECIMAL(20,2) DEFAULT NULL COMMENT "自由现金流(元)" AFTER `receivables_turnover`');
CALL `add_column_if_not_exists`('trade_stock_financial', 'dividend_yield', 'DECIMAL(10,4) DEFAULT NULL COMMENT "股息率(%)" AFTER `free_cash_flow`');
CALL `add_column_if_not_exists`('trade_stock_financial', 'ebitda', 'DECIMAL(20,2) DEFAULT NULL COMMENT "息税折旧摊销前利润(元)" AFTER `dividend_yield`');
CALL `add_column_if_not_exists`('trade_stock_financial', 'ev_ebitda', 'DECIMAL(10,4) DEFAULT NULL COMMENT "EV/EBITDA" AFTER `ebitda`');
CALL `add_column_if_not_exists`('trade_stock_financial', 'retained_earnings', 'DECIMAL(20,2) DEFAULT NULL COMMENT "留存收益(元)" AFTER `ev_ebitda`');

-- 扩展 trade_stock_master - 添加更多字段
CALL `add_column_if_not_exists`('trade_stock_master', 'sector_code1', 'VARCHAR(20) DEFAULT NULL COMMENT "申万一级行业代码" AFTER `sector_level2`');
CALL `add_column_if_not_exists`('trade_stock_master', 'sector_code2', 'VARCHAR(20) DEFAULT NULL COMMENT "申万二级行业代码" AFTER `sector_code1`');
CALL `add_column_if_not_exists`('trade_stock_master', 'total_shares', 'BIGINT DEFAULT NULL COMMENT "总股本" AFTER `sector_code2`');
CALL `add_column_if_not_exists`('trade_stock_master', 'float_shares', 'BIGINT DEFAULT NULL COMMENT "流通股本" AFTER `total_shares`');

-- 清理存储过程
DROP PROCEDURE IF EXISTS `add_column_if_not_exists`;

-- ============================================
-- 第八部分: 插入默认数据
-- ============================================

-- 插入默认主力告警规则
INSERT IGNORE INTO `trade_mainforce_alert_rule` (`name`, `rule_type`, `description`, `enabled`, `threshold`, `threshold_unit`, `condition`, `action`, `priority`, `alert_template`, `created_at`) VALUES
('成交量异常告警', 'volume_anomaly', '当日成交量超过过去5日平均成交量的指定倍数时触发告警', 1, 2.0, 'times', '{"avg_days": 5, "volume_ratio_threshold": 2.0}', 'alert', 10, '检测到{stock_name}({stock_code})成交量异常放大，当前成交量是过去5日平均成交量的{ratio}倍', NOW()),
('大单卖出告警', 'large_order', '单笔大单卖出超过指定金额时触发告警', 1, 500000, 'yuan', '{"min_order_amount": 500000, "order_type": "SELL"}', 'alert', 8, '检测到{stock_name}({stock_code})出现大单卖出，单笔成交{amount}元', NOW()),
('主力资金净流出告警', 'netflow', '主力资金净流出超过指定金额时触发告警', 1, 100000000, 'yuan', '{"flow_type": "outflow", "min_amount": 100000000}', 'alert', 9, '检测到{stock_name}({stock_code})主力资金净流出{amount}元，超过安全阈值', NOW()),
('持仓比例异常告警', 'position_change', '主力持仓比例变化超过指定百分比时触发告警', 0, 0.15, 'percent', '{"change_threshold": 0.15, "change_type": "any"}', 'alert', 7, '检测到{stock_name}({stock_code})主力持仓比例变化{ratio}%，超过阈值', NOW());

-- 插入默认审批流程模板
INSERT IGNORE INTO `trade_approval_template` (`id`, `name`, `description`, `status`, `nodes`, `edges`, `created_at`) VALUES
('template_001', '交易风控审批', '股票交易风控审批流程', 'active',
 '[{"id":"node_start","type":"start","label":"开始","x":100,"y":200},{"id":"node_approver_1","type":"approver","label":"风控经理审批","x":300,"y":200,"approver_type":"role","approver_id":"risk_manager","approver_name":"风控经理"},{"id":"node_end","type":"end","label":"结束","x":500,"y":200}]',
 '[{"id":"edge_1","source":"node_start","target":"node_approver_1"},{"id":"edge_2","source":"node_approver_1","target":"node_end"}]',
 NOW());

-- ============================================
-- 第九部分: 验证
-- ============================================

SELECT '====================================' AS '';
SELECT '数据库迁移验证' AS '';
SELECT '====================================' AS '';

-- 验证新建表
SELECT '信号中心' AS module, COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN ('trade_signal_rule', 'trade_signal_rule_condition', 'trade_signal_record', 'trade_signal_snapshot', 'trade_signal_statistic')
UNION ALL
SELECT '绩效报告', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN ('trade_performance_report', 'trade_backtest_record')
UNION ALL
SELECT '模拟盘', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN ('trade_sim_account', 'trade_sim_position', 'trade_sim_trade')
UNION ALL
SELECT '风控看板', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN ('trade_risk_event', 'trade_risk_alert', 'trade_risk_operation_log', 'trade_position_risk', 'trade_account_risk_metric')
UNION ALL
SELECT '主力识别', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN ('trade_mainforce_activity', 'trade_mainforce_task', 'trade_mainforce_position_change', 'trade_kline_marker', 'trade_mainforce_alert_rule', 'trade_mainforce_statistic', 'trade_mainforce_flow')
UNION ALL
SELECT '审批流程', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name IN ('trade_approval_template', 'trade_approval_instance', 'trade_approval_node_instance', 'trade_approval_record');

-- 验证扩展字段
SELECT 'trade_stock_financial' AS tbl, COUNT(*) AS new_fields
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_stock_financial'
  AND column_name IN ('operating_margin', 'quick_ratio', 'total_asset_turnover', 'free_cash_flow', 'dividend_yield', 'ebitda', 'ev_ebitda')
UNION ALL
SELECT 'trade_risk_rule', COUNT(*)
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_risk_rule'
  AND column_name IN ('trigger_count', 'last_trigger_time', 'last_trigger_value', 'status', 'created_by');

SELECT '====================================' AS '';
SELECT '数据库迁移完成' AS '';
SELECT '====================================' AS '';
