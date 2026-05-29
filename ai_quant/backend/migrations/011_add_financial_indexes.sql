-- 为 trade_stock_financial 表添加索引，提升基本面选股查询性能
-- 创建时间: 2026-05-29

ALTER TABLE trade_stock_financial ADD INDEX idx_financial_stock_date (stock_code, report_date);
ALTER TABLE trade_stock_financial ADD INDEX idx_financial_pe_ttm (pe_ttm);
ALTER TABLE trade_stock_financial ADD INDEX idx_financial_roe (roe);
ALTER TABLE trade_stock_financial ADD INDEX idx_financial_market_cap (market_cap);
ALTER TABLE trade_stock_financial ADD INDEX idx_financial_report_date (report_date);
