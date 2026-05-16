-- =============================================================================
-- AI 量化交易系统 - 风控管理数据库扩展方案
-- 版本: 007
-- 创建日期: 2026-05-15
-- 作者: AI 助手
-- 描述: 风控看板数据库表结构设计（优化版）
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 第一部分：新建核心表
-- -----------------------------------------------------------------------------

-- 1. 创建风控规则表
CREATE TABLE IF NOT EXISTS `risk_rules` (
    `id` VARCHAR(64) PRIMARY KEY COMMENT '规则ID',
    `name` VARCHAR(255) NOT NULL COMMENT '规则名称',
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
    `created_by` VARCHAR(64) COMMENT '创建人',
    INDEX `idx_rule_type` (`rule_type`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控规则表';

-- 2. 创建风控告警表
CREATE TABLE IF NOT EXISTS `risk_alerts` (
    `id` VARCHAR(64) PRIMARY KEY COMMENT '告警ID',
    `alert_type` ENUM('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity', 'price_alert', 'volatility', 'system') NOT NULL COMMENT '告警类型',
    `level` ENUM('red', 'orange', 'yellow', 'green') NOT NULL COMMENT '告警级别(红色紧急,橙色重要,黄色一般,绿色正常)',
    `stock_code` VARCHAR(20) COMMENT '股票代码',
    `stock_name` VARCHAR(100) COMMENT '股票名称',
    `account_id` INT COMMENT '关联账户ID',
    `message` TEXT NOT NULL COMMENT '告警消息',
    `metric_value` DECIMAL(20, 4) COMMENT '触发时的指标值',
    `threshold_value` DECIMAL(20, 4) COMMENT '阈值',
    `status` ENUM('pending', 'confirmed', 'ignored', 'processed') NOT NULL DEFAULT 'pending' COMMENT '处理状态',
    `handler_id` VARCHAR(64) COMMENT '处理人ID',
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
    INDEX `idx_is_read` (`is_read`),
    INDEX `idx_account_status_time` (`account_id`, `status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控告警表';

-- 3. 创建风险事件表
CREATE TABLE IF NOT EXISTS `risk_events` (
    `id` VARCHAR(64) PRIMARY KEY COMMENT '事件ID',
    `event_type` ENUM('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity', 'price_alert', 'volatility') NOT NULL COMMENT '事件类型',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') NOT NULL COMMENT '风险等级',
    `stock_code` VARCHAR(20) COMMENT '股票代码',
    `stock_name` VARCHAR(100) COMMENT '股票名称',
    `position_id` INT COMMENT '持仓记录ID',
    `account_id` INT NOT NULL COMMENT '账户ID',
    `description` TEXT COMMENT '事件描述',
    `event_data` JSON COMMENT '事件详情(JSON)',
    `triggered_rule_id` VARCHAR(64) COMMENT '触发的规则ID',
    `status` ENUM('pending', 'confirmed', 'ignored', 'processed', 'expired') NOT NULL DEFAULT 'pending' COMMENT '处理状态',
    `handler_id` VARCHAR(64) COMMENT '处理人ID',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风险事件表';

-- 4. 创建风控操作日志表
CREATE TABLE IF NOT EXISTS `risk_operation_logs` (
    `id` VARCHAR(64) PRIMARY KEY COMMENT '日志ID',
    `operator_id` VARCHAR(64) NOT NULL COMMENT '操作人ID',
    `operator_name` VARCHAR(100) COMMENT '操作人姓名',
    `operation_type` ENUM('create_rule', 'update_rule', 'delete_rule', 'handle_alert', 'confirm_alert', 'ignore_alert', 'process_alert', 'modify_threshold') NOT NULL COMMENT '操作类型',
    `target_type` ENUM('rule', 'alert', 'event', 'account') NOT NULL COMMENT '操作对象类型',
    `target_id` VARCHAR(64) NOT NULL COMMENT '操作对象ID',
    `target_name` VARCHAR(255) COMMENT '操作对象名称',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控操作日志表';

-- -----------------------------------------------------------------------------
-- 第二部分：扩展现有表
-- -----------------------------------------------------------------------------

-- 5. 扩展 sim_position 表 - 添加持仓风险字段
ALTER TABLE `sim_position`
ADD COLUMN `risk_value` DECIMAL(10, 2) DEFAULT 0 COMMENT '风险值(0-100)' AFTER `pnl_pct`,
ADD COLUMN `risk_level` ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low' COMMENT '风险等级' AFTER `risk_value`,
ADD COLUMN `var_95` DECIMAL(20, 4) COMMENT 'VaR 95%置信度' AFTER `risk_level`,
ADD COLUMN `volatility` DECIMAL(10, 4) COMMENT '波动率' AFTER `var_95`,
ADD COLUMN `beta` DECIMAL(10, 4) COMMENT 'Beta值' AFTER `volatility`,
ADD COLUMN `max_loss_rate` DECIMAL(10, 4) COMMENT '最大亏损率' AFTER `beta`,
ADD COLUMN `stop_loss_price` DECIMAL(20, 4) COMMENT '止损价' AFTER `max_loss_rate`,
ADD INDEX `idx_risk_level` (`risk_level`),
ADD INDEX `idx_risk_value` (`risk_value`);

-- 6. 扩展 sim_account 表 - 添加账户风险指标字段
ALTER TABLE `sim_account`
ADD COLUMN `leverage_ratio` DECIMAL(10, 4) DEFAULT 1.0 COMMENT '杠杆率' AFTER `today_pnl_pct`,
ADD COLUMN `liquidity_ratio` DECIMAL(10, 4) DEFAULT 2.0 COMMENT '流动性比率' AFTER `leverage_ratio`,
ADD COLUMN `risk_score` DECIMAL(10, 2) DEFAULT 0 COMMENT '风险评分(0-100)' AFTER `liquidity_ratio`,
ADD COLUMN `risk_level` ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low' COMMENT '风险等级' AFTER `risk_score`,
ADD COLUMN `concentration_ratio` DECIMAL(10, 4) COMMENT '集中度' AFTER `risk_level`,
ADD COLUMN `margin_ratio` DECIMAL(10, 4) COMMENT '保证金比例' AFTER `concentration_ratio`,
ADD INDEX `idx_risk_score` (`risk_score`),
ADD INDEX `idx_risk_level` (`risk_level`);

-- -----------------------------------------------------------------------------
-- 第三部分：初始化示例数据
-- -----------------------------------------------------------------------------

-- 插入风控规则示例数据
INSERT INTO `risk_rules` (`id`, `name`, `description`, `rule_type`, `condition`, `action`, `status`, `priority`, `trigger_count`) VALUES
('rule_001', '止损规则', '单只股票亏损超过8%时触发止损', 'stop_loss', '{"max_loss_rate": 8}', 'alert', 'active', 100, 156),
('rule_002', '仓位上限规则', '单只股票持仓占比不超过15%', 'position_limit', '{"max_position_ratio": 15}', 'alert', 'active', 90, 89),
('rule_003', '流动性规则', '账户流动性比率不低于1.5', 'liquidity', '{"min_liquidity_ratio": 1.5}', 'alert', 'active', 80, 45),
('rule_004', '杠杆率规则', '总杠杆率不超过2倍', 'leverage', '{"max_leverage": 2.0}', 'block', 'triggered', 95, 23),
('rule_005', '行业集中度规则', '单一行业持仓不超过总仓位的30%', 'concentration', '{"max_industry_ratio": 30}', 'alert', 'inactive', 70, 12);

-- 插入告警示例数据
INSERT INTO `risk_alerts` (`id`, `alert_type`, `level`, `stock_code`, `stock_name`, `account_id`, `message`, `metric_value`, `threshold_value`, `status`) VALUES
('alert_001', 'stop_loss', 'red', '600519.SH', '贵州茅台', 1, '股价下跌超过8%，触发止损线', 10.5, 8.0, 'pending'),
('alert_002', 'position_overflow', 'orange', '300750.SZ', '宁德时代', 1, '持仓占比超过15%上限', 15.5, 15.0, 'pending'),
('alert_003', 'liquidity', 'yellow', '000001.SZ', '平安银行', 1, '流动性比率低于安全线', 1.2, 1.5, 'confirmed');

-- -----------------------------------------------------------------------------
-- 第四部分：验证
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '数据库扩展验证' AS '';
SELECT '====================================' AS '';

-- 验证新表
SELECT 'risk_rules' AS tbl, COUNT(*) AS exists_flag
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'risk_rules'
UNION ALL
SELECT 'risk_alerts', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'risk_alerts'
UNION ALL
SELECT 'risk_events', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'risk_events'
UNION ALL
SELECT 'risk_operation_logs', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'risk_operation_logs';

-- 验证扩展字段
SELECT 'sim_position' AS tbl, COUNT(*) AS has_risk_fields
FROM information_schema.columns
WHERE table_schema = DATABASE() 
  AND table_name = 'sim_position'
  AND column_name IN ('risk_value', 'risk_level', 'var_95', 'volatility', 'beta')
UNION ALL
SELECT 'sim_account', COUNT(*)
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'sim_account'
  AND column_name IN ('leverage_ratio', 'liquidity_ratio', 'risk_score', 'risk_level');

-- 统计示例数据
SELECT COUNT(*) AS risk_rules_count FROM risk_rules;
SELECT COUNT(*) AS risk_alerts_count FROM risk_alerts;

SELECT '====================================' AS '';
SELECT '数据库扩展完成' AS '';
SELECT '====================================' AS '';
