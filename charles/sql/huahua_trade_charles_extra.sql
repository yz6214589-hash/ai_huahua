CREATE TABLE IF NOT EXISTS `trade_stock_master` (
  `stock_code` varchar(20) NOT NULL COMMENT '股票代码，如 600519.SH',
  `stock_name` varchar(100) DEFAULT NULL COMMENT '企业名称',
  `source` varchar(20) DEFAULT 'akshare' COMMENT 'qmt/akshare/manual',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`stock_code`),
  KEY `idx_stock_master_name` (`stock_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票主数据（代码-名称映射）';

CREATE TABLE IF NOT EXISTS `trade_job_schedule` (
  `domain` varchar(32) NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `cron` varchar(64) NOT NULL,
  `timezone` varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
  `mode` varchar(10) DEFAULT NULL,
  `params_json` text,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采集任务调度配置';

CREATE TABLE IF NOT EXISTS `trade_watchlist` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(20) NOT NULL,
  `pinned` tinyint(1) NOT NULL DEFAULT 0,
  `sort_order` int(11) NOT NULL DEFAULT 0,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_watchlist_code` (`stock_code`),
  KEY `idx_watchlist_sort` (`pinned`,`sort_order`,`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自选股列表';
