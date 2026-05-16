-- ============================================
-- 主力识别功能数据库表结构 (SQLite版本)
-- 版本: 1.0.0
-- 描述: 支持主力识别、K线标注、活动列表和风控规则
-- 创建时间: 2026-05-15
-- ============================================

-- ============================================
-- 1. 主力活动记录表
-- 存储识别到的主力活动（买入/卖出）
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_activities` (
    `id` TEXT PRIMARY KEY,
    `date` DATE NOT NULL,
    `stock_code` TEXT NOT NULL,
    `stock_name` TEXT NOT NULL,
    `activity_type` TEXT NOT NULL,
    `volume` INTEGER NOT NULL,
    `amount` REAL NOT NULL,
    `price` REAL NOT NULL,
    `ratio` REAL NOT NULL,
    `mainforce_type` TEXT NOT NULL DEFAULT 'retail',
    `description` TEXT,
    `indicators` TEXT,
    `is_anomaly` INTEGER NOT NULL DEFAULT 0,
    `alert_status` TEXT NOT NULL DEFAULT 'none',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS `idx_ma_date` ON `mainforce_activities`(`date`);
CREATE INDEX IF NOT EXISTS `idx_ma_stock_code` ON `mainforce_activities`(`stock_code`);
CREATE INDEX IF NOT EXISTS `idx_ma_activity_type` ON `mainforce_activities`(`activity_type`);
CREATE INDEX IF NOT EXISTS `idx_ma_mainforce_type` ON `mainforce_activities`(`mainforce_type`);
CREATE INDEX IF NOT EXISTS `idx_ma_created_at` ON `mainforce_activities`(`created_at`);
CREATE INDEX IF NOT EXISTS `idx_ma_alert_status` ON `mainforce_activities`(`alert_status`);

-- ============================================
-- 2. 主力识别任务表
-- 存储主力识别任务的配置和运行结果
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_tasks` (
    `id` TEXT PRIMARY KEY,
    `stock_code` TEXT NOT NULL,
    `company_name` TEXT,
    `mode` TEXT NOT NULL DEFAULT 'simulated',
    `params` TEXT NOT NULL,
    `status` TEXT NOT NULL DEFAULT 'pending',
    `result` TEXT,
    `error_message` TEXT,
    `triggered_rule_id` TEXT,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS `idx_mt_stock_code` ON `mainforce_tasks`(`stock_code`);
CREATE INDEX IF NOT EXISTS `idx_mt_status` ON `mainforce_tasks`(`status`);
CREATE INDEX IF NOT EXISTS `idx_mt_created_at` ON `mainforce_tasks`(`created_at`);

-- ============================================
-- 3. 主力持仓变化表
-- 存储主力持仓比例的变化
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_position_changes` (
    `id` TEXT PRIMARY KEY,
    `stock_code` TEXT NOT NULL,
    `stock_name` TEXT NOT NULL,
    `position_date` DATE NOT NULL,
    `position_ratio` REAL NOT NULL,
    `position_change` REAL NOT NULL,
    `position_value` REAL,
    `change_type` TEXT NOT NULL,
    `reason` TEXT,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(`stock_code`, `position_date`)
);

CREATE INDEX IF NOT EXISTS `idx_mpc_stock_code` ON `mainforce_position_changes`(`stock_code`);
CREATE INDEX IF NOT EXISTS `idx_mpc_position_date` ON `mainforce_position_changes`(`position_date`);
CREATE INDEX IF NOT EXISTS `idx_mpc_change_type` ON `mainforce_position_changes`(`change_type`);

-- ============================================
-- 4. K线标注表
-- 存储K线图上的主力活动标注
-- ============================================
CREATE TABLE IF NOT EXISTS `kline_markers` (
    `id` TEXT PRIMARY KEY,
    `stock_code` TEXT NOT NULL,
    `stock_name` TEXT NOT NULL,
    `marker_date` DATE NOT NULL,
    `marker_price` REAL NOT NULL,
    `marker_type` TEXT NOT NULL,
    `volume` INTEGER,
    `amount` REAL,
    `mainforce_type` TEXT NOT NULL DEFAULT 'retail',
    `source` TEXT NOT NULL DEFAULT 'auto',
    `activity_id` TEXT,
    `description` TEXT,
    `is_visible` INTEGER NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(`stock_code`, `marker_date`, `marker_type`)
);

CREATE INDEX IF NOT EXISTS `idx_km_stock_code` ON `kline_markers`(`stock_code`);
CREATE INDEX IF NOT EXISTS `idx_km_marker_date` ON `kline_markers`(`marker_date`);
CREATE INDEX IF NOT EXISTS `idx_km_marker_type` ON `kline_markers`(`marker_type`);
CREATE INDEX IF NOT EXISTS `idx_km_source` ON `kline_markers`(`source`);
CREATE INDEX IF NOT EXISTS `idx_km_is_visible` ON `kline_markers`(`is_visible`);

-- ============================================
-- 5. 主力告警规则表
-- 存储主力活动告警规则配置
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_alert_rules` (
    `id` TEXT PRIMARY KEY,
    `name` TEXT NOT NULL,
    `rule_type` TEXT NOT NULL,
    `description` TEXT,
    `enabled` INTEGER NOT NULL DEFAULT 1,
    `threshold` REAL NOT NULL,
    `threshold_unit` TEXT,
    `condition` TEXT,
    `action` TEXT NOT NULL DEFAULT 'alert',
    `priority` INTEGER NOT NULL DEFAULT 0,
    `trigger_count` INTEGER NOT NULL DEFAULT 0,
    `last_trigger_time` DATETIME,
    `last_trigger_value` REAL,
    `alert_template` TEXT,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `created_by` TEXT
);

CREATE INDEX IF NOT EXISTS `idx_mar_rule_type` ON `mainforce_alert_rules`(`rule_type`);
CREATE INDEX IF NOT EXISTS `idx_mar_enabled` ON `mainforce_alert_rules`(`enabled`);
CREATE INDEX IF NOT EXISTS `idx_mar_priority` ON `mainforce_alert_rules`(`priority`);
CREATE INDEX IF NOT EXISTS `idx_mar_created_at` ON `mainforce_alert_rules`(`created_at`);

-- ============================================
-- 6. 主力识别统计表
-- 存储每日主力识别统计汇总
-- ============================================
CREATE TABLE IF NOT EXISTS `mainforce_statistics` (
    `id` TEXT PRIMARY KEY,
    `stat_date` DATE NOT NULL UNIQUE,
    `buy_count` INTEGER NOT NULL DEFAULT 0,
    `sell_count` INTEGER NOT NULL DEFAULT 0,
    `total_buy_amount` REAL NOT NULL DEFAULT 0,
    `total_sell_amount` REAL NOT NULL DEFAULT 0,
    `net_flow` REAL NOT NULL DEFAULT 0,
    `institution_buy_count` INTEGER NOT NULL DEFAULT 0,
    `hot_money_buy_count` INTEGER NOT NULL DEFAULT 0,
    `retail_sell_count` INTEGER NOT NULL DEFAULT 0,
    `anomaly_count` INTEGER NOT NULL DEFAULT 0,
    `alert_count` INTEGER NOT NULL DEFAULT 0,
    `top_stocks` TEXT,
    `summary` TEXT,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS `idx_ms_stat_date` ON `mainforce_statistics`(`stat_date`);

-- ============================================
-- 插入默认的主力告警规则
-- ============================================
INSERT INTO `mainforce_alert_rules` (`id`, `name`, `rule_type`, `description`, `enabled`, `threshold`, `threshold_unit`, `condition`, `action`, `priority`, `alert_template`, `created_at`) VALUES
(
    lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6))),
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
    datetime('now')
);

INSERT INTO `mainforce_alert_rules` (`id`, `name`, `rule_type`, `description`, `enabled`, `threshold`, `threshold_unit`, `condition`, `action`, `priority`, `alert_template`, `created_at`) VALUES
(
    lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6))),
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
    datetime('now')
);

INSERT INTO `mainforce_alert_rules` (`id`, `name`, `rule_type`, `description`, `enabled`, `threshold`, `threshold_unit`, `condition`, `action`, `priority`, `alert_template`, `created_at`) VALUES
(
    lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6))),
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
    datetime('now')
);

INSERT INTO `mainforce_alert_rules` (`id`, `name`, `rule_type`, `description`, `enabled`, `threshold`, `threshold_unit`, `condition`, `action`, `priority`, `alert_template`, `created_at`) VALUES
(
    lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6))),
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
    datetime('now')
);
