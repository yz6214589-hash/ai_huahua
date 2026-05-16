-- =============================================================================
-- AI 量化交易系统 - 风控管理数据库扩展方案
-- 版本: 009
-- 创建日期: 2026-05-15
-- 作者: AI 助手
-- 数据库: huahua_trade (腾讯云 CDB)
-- =============================================================================

SELECT '====================================' AS '';
SELECT '开始执行风控管理数据库扩展 V009' AS '迁移状态';
SELECT '执行时间:' AS '', NOW() AS '';
SELECT '数据库: huahua_trade (腾讯云 CDB)' AS '数据库信息';
SELECT '====================================' AS '';

-- -----------------------------------------------------------------------------
-- 第一部分：新建表
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '第一部分：创建风控相关表' AS '步骤';
SELECT '====================================' AS '';

-- 1. 创建风控告警表
SELECT '创建表: risk_alerts (风控告警表)' AS '';

CREATE TABLE IF NOT EXISTS `risk_alerts` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `alert_code` VARCHAR(64) UNIQUE COMMENT '告警编号',
    `alert_type` ENUM('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity', 'system') NOT NULL COMMENT '告警类型',
    `level` ENUM('red', 'orange', 'yellow', 'green') NOT NULL COMMENT '告警级别(红色紧急,橙色重要,黄色一般,绿色正常)',
    `stock_code` VARCHAR(20) COMMENT '股票代码',
    `stock_name` VARCHAR(100) COMMENT '股票名称',
    `account_id` VARCHAR(32) COMMENT '账户ID',
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
    INDEX `idx_account_id` (`account_id`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_is_read` (`is_read`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控告警表';

-- 2. 创建风险事件表
SELECT '创建表: risk_events (风险事件表)' AS '';

CREATE TABLE IF NOT EXISTS `risk_events` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `event_code` VARCHAR(64) UNIQUE COMMENT '事件编号',
    `event_type` ENUM('stop_loss', 'position_overflow', 'liquidity', 'mainforce_activity') NOT NULL COMMENT '事件类型',
    `risk_level` ENUM('low', 'medium', 'high', 'critical') NOT NULL COMMENT '风险等级',
    `stock_code` VARCHAR(20) COMMENT '股票代码',
    `stock_name` VARCHAR(100) COMMENT '股票名称',
    `position_id` BIGINT COMMENT '持仓记录ID',
    `account_id` VARCHAR(32) NOT NULL COMMENT '账户ID',
    `description` TEXT COMMENT '事件描述',
    `event_data` JSON COMMENT '事件详情(JSON)',
    `triggered_rule_id` BIGINT COMMENT '触发的规则ID',
    `status` ENUM('pending', 'confirmed', 'ignored', 'processed', 'expired') NOT NULL DEFAULT 'pending' COMMENT '处理状态',
    `handler_id` VARCHAR(64) COMMENT '处理人ID',
    `handle_comment` TEXT COMMENT '处理意见',
    `handled_at` DATETIME COMMENT '处理时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_event_type` (`event_type`),
    INDEX `idx_risk_level` (`risk_level`),
    INDEX `idx_status` (`status`),
    INDEX `idx_account_id` (`account_id`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_triggered_rule_id` (`triggered_rule_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风险事件表';

-- 3. 创建风控操作日志表
SELECT '创建表: risk_operation_logs (风控操作日志表)' AS '';

CREATE TABLE IF NOT EXISTS `risk_operation_logs` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `operator_id` VARCHAR(64) NOT NULL COMMENT '操作人ID',
    `operator_name` VARCHAR(100) COMMENT '操作人姓名',
    `operation_type` ENUM('create_rule', 'update_rule', 'delete_rule', 'handle_alert', 'confirm_alert', 'ignore_alert', 'process_alert') NOT NULL COMMENT '操作类型',
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
    INDEX `idx_target` (`target_type`, `target_id`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控操作日志表';

-- -----------------------------------------------------------------------------
-- 第二部分：扩展现有表
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '第二部分：扩展现有表' AS '步骤';
SELECT '====================================' AS '';

-- 4. 扩展 trade_live_position 表 - 添加持仓风险字段
SELECT '扩展表: trade_live_position (添加持仓风险字段)' AS '';

ALTER TABLE `trade_live_position`
ADD COLUMN `risk_value` DECIMAL(10, 2) DEFAULT 0 COMMENT '风险值(0-100)' AFTER `profit_loss_pct`,
ADD COLUMN `risk_level` ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low' COMMENT '风险等级' AFTER `risk_value`,
ADD COLUMN `var_95` DECIMAL(20, 4) COMMENT 'VaR 95%置信度' AFTER `risk_level`,
ADD COLUMN `volatility` DECIMAL(10, 4) COMMENT '波动率' AFTER `var_95`,
ADD COLUMN `beta` DECIMAL(10, 4) COMMENT 'Beta值' AFTER `volatility`,
ADD INDEX `idx_risk_level` (`risk_level`),
ADD INDEX `idx_risk_value` (`risk_value`);

-- 5. 扩展 trade_risk_rule 表 - 添加触发统计字段
SELECT '扩展表: trade_risk_rule (添加触发统计字段)' AS '';

ALTER TABLE `trade_risk_rule`
ADD COLUMN `trigger_count` INT DEFAULT 0 COMMENT '累计触发次数' AFTER `circuit_breaker_pct`,
ADD COLUMN `last_trigger_time` DATETIME COMMENT '最后触发时间' AFTER `trigger_count`,
ADD COLUMN `last_trigger_value` VARCHAR(100) COMMENT '最后触发时的值' AFTER `last_trigger_time`,
ADD COLUMN `action` ENUM('alert', 'block', 'auto_close') DEFAULT 'alert' COMMENT '触发动作' AFTER `decision`,
ADD COLUMN `alert_template` TEXT COMMENT '告警消息模板' AFTER `condition_desc`;

-- -----------------------------------------------------------------------------
-- 第三部分：迁移校验
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '第三部分：迁移校验' AS '步骤';
SELECT '====================================' AS '';

-- 校验新表
SELECT 'risk_alerts' AS tbl, COUNT(*) AS exists_flag
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

-- 校验扩展字段
SELECT 'trade_live_position' AS tbl,
       GROUP_CONCAT(COLUMN_NAME) AS risk_columns
FROM information_schema.columns
WHERE table_schema = DATABASE() 
  AND table_name = 'trade_live_position'
  AND COLUMN_NAME IN ('risk_value', 'risk_level', 'var_95', 'volatility', 'beta')
UNION ALL
SELECT 'trade_risk_rule',
       GROUP_CONCAT(COLUMN_NAME)
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_risk_rule'
  AND COLUMN_NAME IN ('trigger_count', 'last_trigger_time', 'last_trigger_value', 'action', 'alert_template');

-- -----------------------------------------------------------------------------
-- 第四部分：初始化示例数据
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '第四部分：初始化示例数据' AS '步骤';
SELECT '====================================' AS '';

-- 插入风控规则示例
INSERT INTO `trade_risk_rule` (`rule_code`, `rule_name`, `rule_type`, `decision`, `condition_expr`, `condition_desc`, `max_position_pct`, `max_single_loss_pct`, `max_daily_loss_pct`, `circuit_breaker_pct`, `priority`, `enabled`, `trigger_count`, `action`, `alert_template`) VALUES
('rule_001', '止损规则', 'stop_loss', 'alert', 'loss_rate > 0.08', '单只股票亏损超过8%时触发止损', 100, 8, NULL, 20, 100, 1, 156, 'alert', '【止损告警】{stock_name}股价下跌{loss_rate}%，已触发止损规则，请及时处理'),
('rule_002', '仓位上限规则', 'position_limit', 'alert', 'position_ratio > 0.15', '单只股票持仓占比不超过15%', 15, NULL, NULL, NULL, 90, 1, 89, 'alert', '【仓位超限】{stock_name}持仓占比{position_ratio}%，超过上限15%'),
('rule_003', '流动性规则', 'liquidity', 'alert', 'liquidity_ratio < 1.5', '账户流动性比率不低于1.5', NULL, NULL, NULL, NULL, 80, 1, 45, 'alert', '【流动性告警】流动性比率{liquidity_ratio}，低于安全线1.5'),
('rule_004', '杠杆率规则', 'leverage', 'block', 'leverage_ratio > 2.0', '总杠杆率不超过2倍', NULL, NULL, NULL, NULL, 95, 1, 23, 'block', '【杠杆率告警】杠杆率{leverage_ratio}，超过上限2.0倍，禁止开仓'),
('rule_005', '行业集中度规则', 'concentration', 'alert', 'concentration_ratio > 0.30', '单一行业持仓不超过总仓位的30%', NULL, NULL, NULL, NULL, 70, 0, 12, 'alert', '【集中度告警】{industry}行业持仓占比{concentration_ratio}%，超过上限30%');

-- 插入告警示例
INSERT INTO `risk_alerts` (`alert_code`, `alert_type`, `level`, `stock_code`, `stock_name`, `account_id`, `message`, `metric_value`, `threshold_value`, `status`) VALUES
('alert_001', 'stop_loss', 'red', '600519.SH', '贵州茅台', 'SIM', '股价下跌超过8%，触发止损线', 10.5, 8.0, 'pending'),
('alert_002', 'position_overflow', 'orange', '300750.SZ', '宁德时代', 'SIM', '持仓占比超过15%上限', 15.5, 15.0, 'pending'),
('alert_003', 'liquidity', 'yellow', '000001.SZ', '平安银行', 'SIM', '流动性比率低于安全线', 1.2, 1.5, 'confirmed');

-- 插入风险事件示例
INSERT INTO `risk_events` (`event_code`, `event_type`, `risk_level`, `stock_code`, `stock_name`, `account_id`, `description`, `status`) VALUES
('event_001', 'stop_loss', 'critical', '600519.SH', '贵州茅台', 'SIM', '股价下跌触发止损规则', 'pending'),
('event_002', 'position_overflow', 'high', '300750.SZ', '宁德时代', 'SIM', '持仓占比超过上限', 'pending'),
('event_003', 'liquidity', 'medium', '000001.SZ', '平安银行', 'SIM', '流动性比率过低', 'processed');

-- -----------------------------------------------------------------------------
-- 统计示例数据
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '统计示例数据' AS '';
SELECT '====================================' AS '';

SELECT '风控规则总数' AS '', COUNT(*) AS count FROM trade_risk_rule
UNION ALL
SELECT '告警记录总数', COUNT(*) FROM risk_alerts
UNION ALL
SELECT '风险事件总数', COUNT(*) FROM risk_events
UNION ALL
SELECT '持仓记录总数', COUNT(*) FROM trade_live_position;

-- -----------------------------------------------------------------------------
-- 迁移完成
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '数据库迁移 V009 执行完成' AS '完成状态';
SELECT '完成时间:' AS '', NOW() AS '';
SELECT '====================================' AS '';
