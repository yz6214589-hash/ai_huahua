-- ============================================================
-- 个股分时数据表
-- 描述：存储 A 股股票的分时（1分钟级别）交易数据
-- 创建时间：2025-05-24
-- ============================================================

CREATE TABLE IF NOT EXISTS trade_stock_intraday (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码，如600519.SH',
    trade_date DATE NOT NULL COMMENT '交易日期',
    trade_time VARCHAR(10) NOT NULL COMMENT '交易时间 HH:MM 格式',
    price DECIMAL(18,6) DEFAULT NULL COMMENT '当前分钟价格',
    avg_price DECIMAL(18,6) DEFAULT NULL COMMENT '当前均价（从开盘到当前分钟的成交均价）',
    volume BIGINT DEFAULT NULL COMMENT '当前分钟成交量（股）',
    amount DECIMAL(18,4) DEFAULT NULL COMMENT '当前分钟成交额',
    pre_close DECIMAL(18,6) DEFAULT NULL COMMENT '前一日收盘价',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_stock_date_time (stock_code, trade_date, trade_time),
    INDEX idx_stock_date (stock_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='个股分时数据';
