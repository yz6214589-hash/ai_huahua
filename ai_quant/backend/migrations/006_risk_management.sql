-- 风控管理系统数据库表结构
-- 版本: 1.0.0
-- 描述: 支持风控看板的所有数据存储

-- ============================================
-- 1. 风控规则表
-- ============================================
CREATE TABLE IF NOT EXISTS `risk_rules` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '规则ID(UUID)',
    `name` VARCHAR(100) NOT NULL COMMENT '规则名称',
    `description` TEXT COMMENT '规则描述',
    `rule_type` ENUM('stop_loss', 'position_limit', 'liquidity', 'leverage', 'concentration') NOT NULL COMMENT '规则类型',
    `condition` JSON NOT NULL COMMENT '触发条件(JSON格式)',
    `action` ENUM('alert', 'block', 'auto_close') NOT NULL DEFAULT 'alert' COMMENT '触发动作',
    `status` ENUM('active', 'inactive', 'triggered') NOT NULL DEFAULT 'active' COMMENT '规则状态',
    `priority` INT NOT NULL DEFAULT 0 COMMENT '优先级(数字越大优先级越高)',
    `trigger_count` INT NOT NULL DEFAULT 0 COMMENT '累计触发次数',
    `last_trigger_time` DATETIME COMMENT '最后触发时间',
    `last_trigger_value` VARCHAR(100) COMMENT '最后触发时的值',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `created_by` VARCHAR(36) COMMENT '创建人',
    INDEX `idx_rule_type` (`rule_type`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风控规则表';

-- ============================================
-- 2. 风险事件表
-- ============================================
CREATE TABLE IF NOT EXISTS `risk_events` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '事件ID(UUID)',
    `event_type` ENUM('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity', 'price_alert', 'volatility') NOT NULL COMMENT '事件类型',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') NOT NULL COMMENT '风险等级',
    `stock_code` VARCHAR(20) COMMENT '股票代码(可为NULL)',
    `stock_name` VARCHAR(50) COMMENT '股票名称(可为NULL)',
    `position_id` VARCHAR(36) COMMENT '持仓记录ID(可为NULL)',
    `account_id` VARCHAR(36) COMMENT '账户ID',
    `description` TEXT COMMENT '事件描述',
    `event_data` JSON COMMENT '事件详情(JSON格式)',
    `triggered_rule_id` VARCHAR(36) COMMENT '触发的规则ID',
    `status` ENUM('pending', 'confirmed', 'ignored', 'processed', 'expired') NOT NULL DEFAULT 'pending' COMMENT '处理状态',
    `handler_id` VARCHAR(36) COMMENT '处理人ID',
    `handle_comment` TEXT COMMENT '处理意见',
    `handled_at` DATETIME COMMENT '处理时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_event_type` (`event_type`),
    INDEX `idx_risk_level` (`risk_level`),
    INDEX `idx_status` (`status`),
    INDEX `idx_stock_code` (`stock_code`),
    INDEX `idx_account_id` (`account_id`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_triggered_rule_id` (`triggered_rule_id`),
    FOREIGN KEY (`triggered_rule_id`) REFERENCES `risk_rules`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风险事件表';

-- ============================================
-- 3. 风控告警表
-- ============================================
CREATE TABLE IF NOT EXISTS `risk_alerts` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '告警ID(UUID)',
    `alert_type` ENUM('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity', 'price_alert', 'volatility', 'system') NOT NULL COMMENT '告警类型',
    `level` ENUM('red', 'orange', 'yellow', 'green') NOT NULL COMMENT '告警级别(红色紧急,橙色重要,黄色一般,绿色正常)',
    `stock_code` VARCHAR(20) COMMENT '股票代码(可为NULL)',
    `stock_name` VARCHAR(50) COMMENT '股票名称(可为NULL)',
    `account_id` VARCHAR(36) NOT NULL COMMENT '账户ID',
    `message` TEXT NOT NULL COMMENT '告警消息',
    `metric_value` DECIMAL(20, 4) COMMENT '触发时的指标值',
    `threshold_value` DECIMAL(20, 4) COMMENT '阈值',
    `status` ENUM('pending', 'confirmed', 'ignored', 'processed') NOT NULL DEFAULT 'pending' COMMENT '处理状态',
    `handler_id` VARCHAR(36) COMMENT '处理人ID',
    `handle_result` TEXT COMMENT '处理结果',
    `handled_at` DATETIME COMMENT '处理时间',
    `is_read` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已读',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_alert_type` (`alert_type`),
    INDEX `idx_level` (`level`),
    INDEX `idx_status` (`status`),
    INDEX `idx_stock_code` (`stock_code`),
    INDEX `idx_account_id` (`account_id`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_is_read` (`is_read`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风控告警表';

-- ============================================
-- 4. 持仓风险表
-- ============================================
CREATE TABLE IF NOT EXISTS `position_risks` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '记录ID(UUID)',
    `account_id` VARCHAR(36) NOT NULL COMMENT '账户ID',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(50) NOT NULL COMMENT '股票名称',
    `position_value` DECIMAL(20, 2) NOT NULL COMMENT '持仓市值',
    `position_ratio` DECIMAL(10, 4) NOT NULL COMMENT '持仓占比',
    `risk_value` DECIMAL(10, 2) NOT NULL COMMENT '风险值(0-100)',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') NOT NULL COMMENT '风险等级',
    `var_95` DECIMAL(20, 4) COMMENT 'VaR 95%置信度',
    `volatility` DECIMAL(10, 4) COMMENT '波动率',
    `beta` DECIMAL(10, 4) COMMENT 'Beta值',
    `max_loss_rate` DECIMAL(10, 4) COMMENT '最大亏损率',
    `stop_loss_price` DECIMAL(20, 4) COMMENT '止损价',
    `position_date` DATE NOT NULL COMMENT '持仓日期',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_account_stock_date` (`account_id`, `stock_code`, `position_date`),
    INDEX `idx_account_id` (`account_id`),
    INDEX `idx_risk_level` (`risk_level`),
    INDEX `idx_risk_value` (`risk_value`),
    INDEX `idx_position_date` (`position_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='持仓风险表';

-- ============================================
-- 5. 账户风险指标表
-- ============================================
CREATE TABLE IF NOT EXISTS `account_risk_metrics` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '记录ID(UUID)',
    `account_id` VARCHAR(36) NOT NULL COMMENT '账户ID',
    `total_value` DECIMAL(20, 2) NOT NULL COMMENT '总资产',
    `cash_balance` DECIMAL(20, 2) NOT NULL COMMENT '现金余额',
    `position_value` DECIMAL(20, 2) NOT NULL COMMENT '持仓市值',
    `liability_value` DECIMAL(20, 2) NOT NULL DEFAULT 0 COMMENT '负债值',
    `leverage_ratio` DECIMAL(10, 4) NOT NULL COMMENT '杠杆率',
    `liquidity_ratio` DECIMAL(10, 4) NOT NULL COMMENT '流动性比率',
    `risk_score` DECIMAL(10, 2) NOT NULL COMMENT '风险评分(0-100)',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') NOT NULL COMMENT '风险等级',
    `margin_ratio` DECIMAL(10, 4) COMMENT '保证金比例',
    `concentration_ratio` DECIMAL(10, 4) COMMENT '集中度',
    `net_value` DECIMAL(20, 4) COMMENT '净值',
    `daily_return` DECIMAL(10, 4) COMMENT '日收益率',
    `max_drawdown` DECIMAL(10, 4) COMMENT '最大回撤',
    `record_date` DATE NOT NULL COMMENT '记录日期',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_account_date` (`account_id`, `record_date`),
    INDEX `idx_account_id` (`account_id`),
    INDEX `idx_risk_score` (`risk_score`),
    INDEX `idx_risk_level` (`risk_level`),
    INDEX `idx_record_date` (`record_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账户风险指标表';

-- ============================================
-- 6. 主力资金流表
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_flow` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '记录ID(UUID)',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(50) NOT NULL COMMENT '股票名称',
    `trade_date` DATE NOT NULL COMMENT '交易日期',
    `main_inflow` DECIMAL(20, 2) COMMENT '主力净流入(元)',
    `main_outflow` DECIMAL(20, 2) COMMENT '主力净流出(元)',
    `main_netflow` DECIMAL(20, 2) COMMENT '主力净流入净额(元)',
    `main_inflow_ratio` DECIMAL(10, 4) COMMENT '主力净流入占比',
    `retail_inflow` DECIMAL(20, 2) COMMENT '散户净流入',
    `total_volume` DECIMAL(20, 2) COMMENT '总成交量',
    `close_price` DECIMAL(20, 4) COMMENT '收盘价',
    `price_change` DECIMAL(10, 4) COMMENT '涨跌幅',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_stock_date` (`stock_code`, `trade_date`),
    INDEX `idx_stock_code` (`stock_code`),
    INDEX `idx_trade_date` (`trade_date`),
    INDEX `idx_main_netflow` (`main_netflow`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力资金流表';

-- ============================================
-- 7. 风控操作日志表
-- ============================================
CREATE TABLE IF NOT EXISTS `risk_operation_logs` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '日志ID(UUID)',
    `operator_id` VARCHAR(36) NOT NULL COMMENT '操作人ID',
    `operator_name` VARCHAR(50) COMMENT '操作人姓名',
    `operation_type` ENUM('create_rule', 'update_rule', 'delete_rule', 'handle_alert', 'confirm_alert', 'ignore_alert', 'process_alert', 'modify_threshold') NOT NULL COMMENT '操作类型',
    `target_type` ENUM('rule', 'alert', 'event', 'account') NOT NULL COMMENT '操作对象类型',
    `target_id` VARCHAR(36) NOT NULL COMMENT '操作对象ID',
    `target_name` VARCHAR(100) COMMENT '操作对象名称',
    `old_value` JSON COMMENT '修改前的值',
    `new_value` JSON COMMENT '修改后的值',
    `ip_address` VARCHAR(50) COMMENT 'IP地址',
    `user_agent` VARCHAR(500) COMMENT 'User-Agent',
    `result` ENUM('success', 'failed') NOT NULL COMMENT '操作结果',
    `error_message` TEXT COMMENT '错误信息',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX `idx_operator_id` (`operator_id`),
    INDEX `idx_operation_type` (`operation_type`),
    INDEX `idx_target_type` (`target_type`),
    INDEX `idx_target_id` (`target_id`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风控操作日志表';

-- ============================================
-- 触发器: 自动更新规则的触发次数
-- ============================================
DELIMITER $$

CREATE TRIGGER IF NOT EXISTS `trg_update_rule_trigger_count`
AFTER INSERT ON `risk_events`
FOR EACH ROW
BEGIN
    IF NEW.triggered_rule_id IS NOT NULL THEN
        UPDATE `risk_rules`
        SET
            trigger_count = trigger_count + 1,
            last_trigger_time = NEW.created_at,
            last_trigger_value = JSON_UNQUOTE(JSON_EXTRACT(NEW.event_data, '$.trigger_value')),
            status = 'triggered'
        WHERE id = NEW.triggered_rule_id;
    END IF;
END$$

DELIMITER ;
