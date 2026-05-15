-- 自选股分组功能迁移脚本
-- 创建时间: 2026-05-11

-- 分组表
CREATE TABLE IF NOT EXISTS `trade_watchlist_group` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT '分组名称',
  `sort_order` int(11) NOT NULL DEFAULT '0' COMMENT '排序顺序',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_group_sort` (`sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自选股分组表';

-- 股票-分组关系表（一对多，一支股票可属于多个分组）
CREATE TABLE IF NOT EXISTS `trade_watchlist_item_group` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(20) NOT NULL COMMENT '股票代码',
  `group_id` int(11) NOT NULL COMMENT '分组ID',
  `sort_order` int(11) NOT NULL DEFAULT '0' COMMENT '分组内排序',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_stock_group` (`stock_code`, `group_id`),
  KEY `idx_item_group` (`group_id`),
  KEY `idx_item_stock` (`stock_code`),
  CONSTRAINT `fk_item_group` FOREIGN KEY (`group_id`) REFERENCES `trade_watchlist_group` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自选股与分组的关系表';
