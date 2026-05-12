-- 创建数据库
CREATE DATABASE IF NOT EXISTS `huahua_trade` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `huahua_trade`;

-- 创建表结构

-- 表: ai_quant_report_tasks
DROP TABLE IF EXISTS `ai_quant_report_tasks`;
CREATE TABLE `ai_quant_report_tasks` (
  `task_id` varchar(64) NOT NULL,
  `model` varchar(32) NOT NULL,
  `stock_codes` text,
  `stock_names` text,
  `use_rag` tinyint(1) NOT NULL DEFAULT '1',
  `status` varchar(16) NOT NULL,
  `created_at` datetime NOT NULL,
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  `error_message` text,
  `error_location` varchar(256) DEFAULT NULL,
  `report_path` varchar(512) DEFAULT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`task_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 表: trade_calendar_event
DROP TABLE IF EXISTS `trade_calendar_event`;
CREATE TABLE `trade_calendar_event` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `event_date` date NOT NULL COMMENT '事件日期',
  `event_time` varchar(10) DEFAULT NULL COMMENT '事件时间(HH:MM)',
  `country` varchar(10) NOT NULL DEFAULT 'CN' COMMENT 'CN/US/EU/JP',
  `category` varchar(30) NOT NULL COMMENT 'rate/inflation/employment/gdp/pmi/trade/policy/other',
  `title` varchar(200) NOT NULL,
  `importance` tinyint(4) DEFAULT '2' COMMENT '1=低 2=中 3=高',
  `previous_value` varchar(50) DEFAULT NULL COMMENT '前值',
  `forecast_value` varchar(50) DEFAULT NULL COMMENT '预测值',
  `actual_value` varchar(50) DEFAULT NULL COMMENT '实际值',
  `impact` varchar(200) DEFAULT NULL COMMENT '市场影响说明',
  `ai_prompt` text COMMENT 'AI提问prompt',
  `source` varchar(50) DEFAULT NULL COMMENT 'eastmoney/fred/manual',
  `source_url` varchar(500) DEFAULT NULL,
  `is_recurring` tinyint(4) DEFAULT '0',
  `recurrence_rule` varchar(100) DEFAULT NULL COMMENT '周期规则，如"每月第一个周五"',
  `status` varchar(20) DEFAULT 'upcoming' COMMENT 'upcoming/released/cancelled',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_calendar_date_title` (`event_date`,`title`),
  KEY `idx_calendar_date` (`event_date`),
  KEY `idx_calendar_country` (`country`),
  KEY `idx_calendar_category` (`category`),
  KEY `idx_calendar_importance` (`importance`)
) ENGINE=InnoDB AUTO_INCREMENT=9441 DEFAULT CHARSET=utf8mb4 COMMENT='财经日历事件';

-- 表: trade_job_schedule
DROP TABLE IF EXISTS `trade_job_schedule`;
CREATE TABLE `trade_job_schedule` (
  `domain` varchar(32) NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `cron` varchar(64) NOT NULL,
  `timezone` varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
  `mode` varchar(10) DEFAULT NULL,
  `params_json` text,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 表: trade_macro_indicator
DROP TABLE IF EXISTS `trade_macro_indicator`;
CREATE TABLE `trade_macro_indicator` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `indicator_date` date NOT NULL COMMENT '指标月份(月末日期)',
  `cpi_yoy` decimal(10,2) DEFAULT NULL COMMENT 'CPI同比(%)',
  `ppi_yoy` decimal(10,2) DEFAULT NULL COMMENT 'PPI同比(%)',
  `pmi` decimal(10,2) DEFAULT NULL COMMENT 'PMI',
  `m2_yoy` decimal(10,2) DEFAULT NULL COMMENT 'M2同比增速(%)',
  `shrzgm` decimal(14,0) DEFAULT NULL COMMENT '社融规模增量(亿元)',
  `lpr_1y` decimal(6,2) DEFAULT NULL COMMENT 'LPR 1年期(%)',
  `lpr_5y` decimal(6,2) DEFAULT NULL COMMENT 'LPR 5年期(%)',
  `data_source` varchar(20) DEFAULT 'akshare',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_macro_date` (`indicator_date`)
) ENGINE=InnoDB AUTO_INCREMENT=121 DEFAULT CHARSET=utf8mb4 COMMENT='月度宏观指标';

-- 表: trade_rate_daily
DROP TABLE IF EXISTS `trade_rate_daily`;
CREATE TABLE `trade_rate_daily` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `rate_date` date NOT NULL COMMENT '日期',
  `cn_bond_10y` decimal(8,4) DEFAULT NULL COMMENT '中国10年期国债收益率(%)',
  `us_bond_10y` decimal(8,4) DEFAULT NULL COMMENT '美国10年期国债收益率(%)',
  `data_source` varchar(20) DEFAULT 'akshare',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_rate_date` (`rate_date`)
) ENGINE=InnoDB AUTO_INCREMENT=9252 DEFAULT CHARSET=utf8mb4 COMMENT='日频利率指标';

-- 表: trade_report_consensus
DROP TABLE IF EXISTS `trade_report_consensus`;
CREATE TABLE `trade_report_consensus` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(20) NOT NULL,
  `broker` varchar(50) DEFAULT NULL COMMENT '券商',
  `report_date` date DEFAULT NULL,
  `rating` varchar(20) DEFAULT NULL COMMENT '买入/增持/中性/减持',
  `target_price` decimal(10,2) DEFAULT NULL,
  `eps_forecast_current` decimal(10,4) DEFAULT NULL COMMENT '当年EPS预测',
  `eps_forecast_next` decimal(10,4) DEFAULT NULL COMMENT '次年EPS预测',
  `revenue_forecast` decimal(20,2) DEFAULT NULL COMMENT '营收预测(亿)',
  `source_file` varchar(500) DEFAULT NULL COMMENT 'PDF文件路径',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_consensus_unique` (`stock_code`,`broker`,`report_date`),
  KEY `idx_consensus_code` (`stock_code`)
) ENGINE=InnoDB AUTO_INCREMENT=5001 DEFAULT CHARSET=utf8mb4 COMMENT='研报一致性预期';

-- 表: trade_report_task
DROP TABLE IF EXISTS `trade_report_task`;
CREATE TABLE `trade_report_task` (
  `task_id` varchar(32) NOT NULL,
  `model` varchar(32) NOT NULL,
  `stock_codes_json` text NOT NULL,
  `stock_names_json` text,
  `status` varchar(16) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  `error_message` text,
  `report_markdown` longtext,
  PRIMARY KEY (`task_id`),
  KEY `idx_report_task_created` (`created_at`),
  KEY `idx_report_task_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 表: trade_sentiment_event
DROP TABLE IF EXISTS `trade_sentiment_event`;
CREATE TABLE `trade_sentiment_event` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `run_id` varchar(32) NOT NULL,
  `stock_code` varchar(20) NOT NULL,
  `stock_name` varchar(100) DEFAULT NULL,
  `source_type` varchar(16) NOT NULL,
  `source_title` varchar(255) DEFAULT NULL,
  `source_url` text,
  `published_at` datetime DEFAULT NULL,
  `event_type` varchar(16) NOT NULL,
  `event_category` varchar(64) NOT NULL,
  `signal_action` varchar(32) NOT NULL,
  `signal_reason` varchar(255) DEFAULT NULL,
  `impact` varchar(255) DEFAULT NULL,
  `confidence` tinyint(1) NOT NULL DEFAULT '3',
  `urgency` varchar(8) NOT NULL DEFAULT '中',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sent_evt_run` (`run_id`),
  KEY `idx_sent_evt_stock` (`stock_code`),
  KEY `idx_sent_evt_type` (`event_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 表: trade_sentiment_news
DROP TABLE IF EXISTS `trade_sentiment_news`;
CREATE TABLE `trade_sentiment_news` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `run_id` varchar(32) NOT NULL,
  `stock_code` varchar(20) NOT NULL,
  `stock_name` varchar(100) DEFAULT NULL,
  `source_type` varchar(16) NOT NULL,
  `title` varchar(255) DEFAULT NULL,
  `url` text,
  `published_at` datetime DEFAULT NULL,
  `content` longtext,
  `sentiment` varchar(16) DEFAULT NULL,
  `strength` tinyint(1) DEFAULT NULL,
  `summary` text,
  `market_impact` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sent_news_run` (`run_id`),
  KEY `idx_sent_news_stock` (`stock_code`),
  KEY `idx_sent_news_pub` (`published_at`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4;

-- 表: trade_sentiment_run
DROP TABLE IF EXISTS `trade_sentiment_run`;
CREATE TABLE `trade_sentiment_run` (
  `run_id` varchar(32) NOT NULL,
  `trigger_type` varchar(16) NOT NULL,
  `stock_codes_json` text NOT NULL,
  `stock_names_json` text,
  `days` int(11) NOT NULL DEFAULT '3',
  `use_llm` tinyint(1) NOT NULL DEFAULT '0',
  `status` varchar(16) NOT NULL,
  `total_events` int(11) NOT NULL DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  `error_message` text,
  PRIMARY KEY (`run_id`),
  KEY `idx_sent_run_created` (`created_at`),
  KEY `idx_sent_run_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 表: trade_stock_daily
DROP TABLE IF EXISTS `trade_stock_daily`;
CREATE TABLE `trade_stock_daily` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(20) NOT NULL COMMENT '股票代码',
  `stock_name` varchar(100) DEFAULT NULL,
  `trade_date` date NOT NULL COMMENT '交易日期',
  `open_price` decimal(10,2) DEFAULT NULL COMMENT '开盘价',
  `high_price` decimal(10,2) DEFAULT NULL COMMENT '最高价',
  `low_price` decimal(10,2) DEFAULT NULL COMMENT '最低价',
  `close_price` decimal(10,2) DEFAULT NULL COMMENT '收盘价(前复权)',
  `volume` bigint(20) DEFAULT NULL COMMENT '成交量(股)',
  `amount` decimal(20,2) DEFAULT NULL COMMENT '成交额(元)',
  `turnover_rate` decimal(10,4) DEFAULT NULL COMMENT '换手率',
  `ma5` decimal(10,4) DEFAULT NULL,
  `ma10` decimal(10,4) DEFAULT NULL,
  `ma20` decimal(10,4) DEFAULT NULL,
  `ma60` decimal(10,4) DEFAULT NULL,
  `vol_ma5` decimal(20,4) DEFAULT NULL,
  `vol_ma20` decimal(20,4) DEFAULT NULL,
  `rsi14` decimal(10,4) DEFAULT NULL,
  `macd_dif` decimal(12,6) DEFAULT NULL,
  `macd_dea` decimal(12,6) DEFAULT NULL,
  `macd_hist` decimal(12,6) DEFAULT NULL,
  `boll_upper` decimal(12,6) DEFAULT NULL,
  `boll_mid` decimal(12,6) DEFAULT NULL,
  `boll_lower` decimal(12,6) DEFAULT NULL,
  `kdj_k` decimal(10,4) DEFAULT NULL,
  `kdj_d` decimal(10,4) DEFAULT NULL,
  `kdj_j` decimal(10,4) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_stock_daily_code_date` (`stock_code`,`trade_date`),
  KEY `idx_stock_daily_code` (`stock_code`),
  KEY `idx_stock_daily_date` (`trade_date`)
) ENGINE=InnoDB AUTO_INCREMENT=11984152 DEFAULT CHARSET=utf8mb4 COMMENT='日K线数据';

-- 表: trade_stock_master
DROP TABLE IF EXISTS `trade_stock_master`;
CREATE TABLE `trade_stock_master` (
  `stock_code` varchar(20) NOT NULL,
  `stock_name` varchar(100) DEFAULT NULL,
  `source` varchar(20) DEFAULT 'akshare',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`stock_code`),
  KEY `idx_stock_master_name` (`stock_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 表: trade_watchlist
DROP TABLE IF EXISTS `trade_watchlist`;
CREATE TABLE `trade_watchlist` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(20) NOT NULL,
  `pinned` tinyint(1) NOT NULL DEFAULT '0',
  `sort_order` int(11) NOT NULL DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_watchlist_code` (`stock_code`),
  KEY `idx_watchlist_sort` (`pinned`,`sort_order`,`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
