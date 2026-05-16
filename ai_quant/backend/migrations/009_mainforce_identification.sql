-- ============================================
-- 主力识别功能数据库表结构
-- 版本: 1.0.0
-- 描述: 支持主力识别、K线标注、活动列表和风控规则
-- 创建时间: 2026-05-15
-- ============================================

-- ============================================
-- 1. 主力活动记录表
-- 存储识别到的主力活动（买入/卖出）
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_activities` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '记录ID(UUID)',
    `date` DATE NOT NULL COMMENT '活动日期',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(50) NOT NULL COMMENT '股票名称',
    `activity_type` ENUM('BUY', 'SELL') NOT NULL COMMENT '活动类型: BUY=买入, SELL=卖出',
    `volume` BIGINT NOT NULL COMMENT '成交量(股)',
    `amount` DECIMAL(20, 2) NOT NULL COMMENT '成交金额(元)',
    `price` DECIMAL(20, 4) NOT NULL COMMENT '成交价格',
    `ratio` DECIMAL(10, 4) NOT NULL COMMENT '大单占比(0-1)',
    `mainforce_type` ENUM('institution', 'hot_money', 'retail') NOT NULL DEFAULT 'retail' COMMENT '主力类型: institution=机构主力, hot_money=游资, retail=散户',
    `description` TEXT COMMENT '活动描述',
    `indicators` JSON COMMENT '识别指标详情(JSON格式)',
    `is_anomaly` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否异常: 0=正常, 1=异常',
    `alert_status` ENUM('none', 'pending', 'triggered') NOT NULL DEFAULT 'none' COMMENT '告警状态',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_date` (`date`),
    INDEX `idx_stock_code` (`stock_code`),
    INDEX `idx_activity_type` (`activity_type`),
    INDEX `idx_mainforce_type` (`mainforce_type`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_alert_status` (`alert_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力活动记录表';

-- ============================================
-- 2. 主力识别任务表
-- 存储主力识别任务的配置和运行结果
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_tasks` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '任务ID(UUID)',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `company_name` VARCHAR(100) COMMENT '公司名称',
    `mode` ENUM('simulated', 'realtime') NOT NULL DEFAULT 'simulated' COMMENT '识别模式: simulated=模拟, realtime=实时',
    `params` JSON NOT NULL COMMENT '任务参数(JSON格式)',
    `status` ENUM('pending', 'running', 'done', 'failed') NOT NULL DEFAULT 'pending' COMMENT '任务状态',
    `result` JSON COMMENT '运行结果(JSON格式)',
    `error_message` TEXT COMMENT '错误信息',
    `triggered_rule_id` VARCHAR(36) COMMENT '触发的告警规则ID',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_stock_code` (`stock_code`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力识别任务表';

-- ============================================
-- 3. 主力持仓变化表
-- 存储主力持仓比例的变化
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_position_changes` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '记录ID(UUID)',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(50) NOT NULL COMMENT '股票名称',
    `position_date` DATE NOT NULL COMMENT '持仓日期',
    `position_ratio` DECIMAL(10, 4) NOT NULL COMMENT '持仓比例(0-1)',
    `position_change` DECIMAL(10, 4) NOT NULL COMMENT '持仓比例变化(相比前一天)',
    `position_value` DECIMAL(20, 2) COMMENT '持仓市值(元)',
    `change_type` ENUM('increase', 'decrease', 'stable') NOT NULL COMMENT '变化类型: increase=增加, decrease=减少, stable=稳定',
    `reason` TEXT COMMENT '变化原因',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY `uk_stock_date` (`stock_code`, `position_date`),
    INDEX `idx_stock_code` (`stock_code`),
    INDEX `idx_position_date` (`position_date`),
    INDEX `idx_change_type` (`change_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力持仓变化表';

-- ============================================
-- 4. K线标注表
-- 存储K线图上的主力活动标注
-- ============================================
CREATE TABLE IF NOT EXISTS `kline_markers` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '标注ID(UUID)',
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name` VARCHAR(50) NOT NULL COMMENT '股票名称',
    `marker_date` DATE NOT NULL COMMENT '标注日期',
    `marker_price` DECIMAL(20, 4) NOT NULL COMMENT '标注价格',
    `marker_type` ENUM('BUY', 'SELL') NOT NULL COMMENT '标注类型: BUY=买入, SELL=卖出',
    `volume` BIGINT COMMENT '成交量(股)',
    `amount` DECIMAL(20, 2) COMMENT '成交金额(元)',
    `mainforce_type` ENUM('institution', 'hot_money', 'retail') NOT NULL DEFAULT 'retail' COMMENT '主力类型',
    `source` ENUM('auto', 'manual') NOT NULL DEFAULT 'auto' COMMENT '标注来源: auto=自动识别, manual=手动标注',
    `activity_id` VARCHAR(36) COMMENT '关联的主力活动ID',
    `description` TEXT COMMENT '标注描述',
    `is_visible` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否显示: 0=隐藏, 1=显示',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_stock_date_type` (`stock_code`, `marker_date`, `marker_type`),
    INDEX `idx_stock_code` (`stock_code`),
    INDEX `idx_marker_date` (`marker_date`),
    INDEX `idx_marker_type` (`marker_type`),
    INDEX `idx_source` (`source`),
    INDEX `idx_is_visible` (`is_visible`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='K线标注表';

-- ============================================
-- 5. 主力告警规则表
-- 存储主力活动告警规则配置
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_alert_rules` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '规则ID(UUID)',
    `name` VARCHAR(100) NOT NULL COMMENT '规则名称',
    `rule_type` ENUM('volume_anomaly', 'large_order', 'netflow', 'position_change') NOT NULL COMMENT '规则类型',
    `description` TEXT COMMENT '规则描述',
    `enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用: 0=禁用, 1=启用',
    `threshold` DECIMAL(20, 4) NOT NULL COMMENT '阈值',
    `threshold_unit` VARCHAR(20) COMMENT '阈值单位: times=倍数, yuan=元, percent=百分比',
    `condition` JSON COMMENT '触发条件(JSON格式)',
    `action` ENUM('alert', 'block', 'auto_close') NOT NULL DEFAULT 'alert' COMMENT '触发动作',
    `priority` INT NOT NULL DEFAULT 0 COMMENT '优先级(数字越大优先级越高)',
    `trigger_count` INT NOT NULL DEFAULT 0 COMMENT '累计触发次数',
    `last_trigger_time` DATETIME COMMENT '最后触发时间',
    `last_trigger_value` DECIMAL(20, 4) COMMENT '最后触发时的值',
    `alert_template` TEXT COMMENT '告警消息模板',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `created_by` VARCHAR(36) COMMENT '创建人',
    INDEX `idx_rule_type` (`rule_type`),
    INDEX `idx_enabled` (`enabled`),
    INDEX `idx_priority` (`priority`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力告警规则表';

-- ============================================
-- 6. 主力识别统计表
-- 存储每日主力识别统计汇总
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_statistics` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '记录ID(UUID)',
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
    `top_stocks` JSON COMMENT '活跃股票列表(JSON格式)',
    `summary` TEXT COMMENT '统计摘要',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_stat_date` (`stat_date`),
    INDEX `idx_stat_date` (`stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主力识别统计表';

-- ============================================
-- 插入默认的主力告警规则
-- ============================================
INSERT INTO `mainforce_alert_rules` (`id`, `name`, `rule_type`, `description`, `enabled`, `threshold`, `threshold_unit`, `condition`, `action`, `priority`, `alert_template`, `created_at`) VALUES
(
    UUID(),
    '成交量异常告警',
    'volume_anomaly',
    '当日成交量超过过去5日平均成交量的指定倍数时触发告警',
    1,
    2.0,
    'times',
    '{"avg_days": 5, "volume_ratio_threshold": 2.0}',
    'alert',
    10,
    '检测到{stock_name}({stock_code})成交量异常放大，当前成交量是过去5日平均成交量的{ratio}倍',
    NOW()
),
(
    UUID(),
    '大单卖出告警',
    'large_order',
    '单笔大单卖出超过指定金额时触发告警',
    1,
    500000,
    'yuan',
    '{"min_order_amount": 500000, "order_type": "SELL"}',
    'alert',
    8,
    '检测到{stock_name}({stock_code})出现大单卖出，单笔成交{amount}元',
    NOW()
),
(
    UUID(),
    '主力资金净流出告警',
    'netflow',
    '主力资金净流出超过指定金额时触发告警',
    1,
    100000000,
    'yuan',
    '{"flow_type": "outflow", "min_amount": 100000000}',
    'alert',
    9,
    '检测到{stock_name}({stock_code})主力资金净流出{amount}元，超过安全阈值',
    NOW()
),
(
    UUID(),
    '持仓比例异常告警',
    'position_change',
    '主力持仓比例变化超过指定百分比时触发告警',
    0,
    0.15,
    'percent',
    '{"change_threshold": 0.15, "change_type": "any"}',
    'alert',
    7,
    '检测到{stock_name}({stock_code})主力持仓比例变化{ratio}%，超过阈值',
    NOW()
);
