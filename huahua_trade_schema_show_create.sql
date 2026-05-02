CREATE DATABASE IF NOT EXISTS `huahua_trade` CHARACTER SET utf8mb4;
USE `huahua_trade`;

-- trade_calendar_event
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
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COMMENT='财经日历事件';

-- trade_macro_indicator
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

-- trade_rate_daily
CREATE TABLE `trade_rate_daily` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `rate_date` date NOT NULL COMMENT '日期',
  `cn_bond_10y` decimal(8,4) DEFAULT NULL COMMENT '中国10年期国债收益率(%)',
  `us_bond_10y` decimal(8,4) DEFAULT NULL COMMENT '美国10年期国债收益率(%)',
  `data_source` varchar(20) DEFAULT 'akshare',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_rate_date` (`rate_date`)
) ENGINE=InnoDB AUTO_INCREMENT=804 DEFAULT CHARSET=utf8mb4 COMMENT='日频利率指标';

-- trade_report_consensus
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
) ENGINE=InnoDB AUTO_INCREMENT=2605 DEFAULT CHARSET=utf8mb4 COMMENT='研报一致性预期';

-- trade_stock_daily
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
) ENGINE=InnoDB AUTO_INCREMENT=1170046 DEFAULT CHARSET=utf8mb4 COMMENT='日K线数据';

-- trade_stock_financial
CREATE TABLE `trade_stock_financial` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(20) NOT NULL,
  `report_date` date NOT NULL COMMENT '报告期，如 2024-12-31',
  `revenue` decimal(20,2) DEFAULT NULL COMMENT '营业收入(元)',
  `net_profit` decimal(20,2) DEFAULT NULL COMMENT '净利润(元)',
  `eps` decimal(10,4) DEFAULT NULL COMMENT '每股收益',
  `roe` decimal(10,4) DEFAULT NULL COMMENT 'ROE(%)',
  `roa` decimal(10,4) DEFAULT NULL COMMENT 'ROA(%)',
  `gross_margin` decimal(10,4) DEFAULT NULL COMMENT '毛利率(%)',
  `net_margin` decimal(10,4) DEFAULT NULL COMMENT '净利率(%)',
  `debt_ratio` decimal(10,4) DEFAULT NULL COMMENT '资产负债率(%)',
  `current_ratio` decimal(10,4) DEFAULT NULL COMMENT '流动比率',
  `operating_cashflow` decimal(20,2) DEFAULT NULL COMMENT '经营现金流(元)',
  `total_assets` decimal(20,2) DEFAULT NULL COMMENT '总资产(元)',
  `total_equity` decimal(20,2) DEFAULT NULL COMMENT '净资产(元)',
  `data_source` varchar(20) DEFAULT 'akshare',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_fina_code_date` (`stock_code`,`report_date`),
  KEY `idx_fina_code` (`stock_code`)
) ENGINE=InnoDB AUTO_INCREMENT=167326 DEFAULT CHARSET=utf8mb4 COMMENT='季度财务数据';

-- trade_stock_news
CREATE TABLE `trade_stock_news` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(20) DEFAULT NULL COMMENT '股票代码',
  `sector_code` varchar(20) DEFAULT NULL COMMENT '板块代码',
  `news_type` varchar(20) NOT NULL COMMENT 'announcement/news/report',
  `title` varchar(500) NOT NULL,
  `content` text,
  `summary` text,
  `source` varchar(50) DEFAULT NULL COMMENT 'eastmoney/cailianshe/kimi',
  `source_url` varchar(500) DEFAULT NULL,
  `published_at` datetime DEFAULT NULL,
  `sentiment` varchar(20) DEFAULT NULL COMMENT 'positive/negative/neutral',
  `sentiment_score` decimal(5,2) DEFAULT NULL COMMENT '-1到1',
  `is_important` tinyint(4) DEFAULT '0',
  `is_read` tinyint(4) DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_stock_news_code` (`stock_code`),
  KEY `idx_stock_news_published` (`published_at`),
  KEY `idx_stock_news_type` (`news_type`)
) ENGINE=InnoDB AUTO_INCREMENT=20015 DEFAULT CHARSET=utf8mb4 COMMENT='新闻事件';
