-- =============================================================================
-- AI 量化投资系统 - 数据库迁移脚本 (V003)
-- 新增：指数日线数据表 trade_index_daily
-- 用途：存储沪深交易所主要指数的日线行情数据，
--       供回测系统的基准指数对比和 Alpha/Beta 指标计算使用。
-- =============================================================================

SELECT '====================================' AS '';
SELECT '开始执行数据库迁移 V003' AS '迁移状态';
SELECT '执行时间:' AS '', NOW() AS '';

-- 校验前置依赖表是否存在
SELECT COUNT(*) AS 'trade_stock_master_exists' FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'trade_stock_master';

-- ---------------------------------------------------------------------------
-- 指数日线数据表 trade_index_daily
-- ---------------------------------------------------------------------------
-- 说明：存储沪深交易所主要指数的日线行情数据。
--       数据来源优先级：QMT Gateway（主） > TuShare（备1） > AKShare（备2）
--       通过唯一索引 (index_code, trade_date) 防止重复数据写入。
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_index_daily` (
    `id`                BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',

    `index_code`        VARCHAR(20) NOT NULL COMMENT '指数代码（如: 000300.SH）',
    `index_name`        VARCHAR(100) NULL COMMENT '指数名称（如: 沪深300）',
    `trade_date`        DATE NOT NULL COMMENT '交易日期',

    `open_price`        DECIMAL(12,4) NULL COMMENT '开盘价',
    `close_price`       DECIMAL(12,4) NOT NULL COMMENT '收盘价',
    `high_price`        DECIMAL(12,4) NULL COMMENT '最高价',
    `low_price`         DECIMAL(12,4) NULL COMMENT '最低价',
    `pre_close_price`   DECIMAL(12,4) NULL COMMENT '前收盘价',
    `change_pct`        DECIMAL(10,4) NULL COMMENT '涨跌幅(%)',

    `volume`            DECIMAL(20,2) NULL COMMENT '成交量（股）',
    `amount`            DECIMAL(20,2) NULL COMMENT '成交额（元）',

    -- 数据源与采集元信息
    `data_source`       VARCHAR(20) NOT NULL DEFAULT 'akshare' COMMENT '数据来源: qmt/tushare/akshare',
    `collected_at`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '采集时间',

    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_index_daily` (`index_code`, `trade_date`),
    KEY `idx_index_daily_code` (`index_code`),
    KEY `idx_index_daily_date` (`trade_date`),
    KEY `idx_index_daily_code_date` (`index_code`, `trade_date`),
    KEY `idx_index_daily_collected` (`collected_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='指数日线数据表（存储沪深交易所主要指数行情，供回测基准对比使用）';

-- ---------------------------------------------------------------------------
-- 迁移完成校验
-- ---------------------------------------------------------------------------

SELECT 'trade_index_daily' AS tbl, COUNT(*) AS cnt FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'trade_index_daily';

SELECT '====================================' AS '';
SELECT '数据库迁移 V003 执行完成' AS '完成状态';
SELECT '完成时间:' AS '', NOW() AS '';
SELECT '====================================' AS '';
