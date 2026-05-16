-- 申万行业分类字段添加（简化版）
-- 为 trade_stock_master 表添加申万一级、二级行业分类字段

-- 添加申万一级行业
ALTER TABLE `trade_stock_master`
    ADD COLUMN IF NOT EXISTS `sector_level1` VARCHAR(50) NULL COMMENT '申万一级行业'
    AFTER `industry_benchmark`;

-- 添加申万二级行业
ALTER TABLE `trade_stock_master`
    ADD COLUMN IF NOT EXISTS `sector_level2` VARCHAR(50) NULL COMMENT '申万二级行业'
    AFTER `sector_level1`;

-- 创建申万行业索引（提高查询性能）
CREATE INDEX IF NOT EXISTS idx_sw_industry_l1 ON trade_stock_master(sector_level1);
CREATE INDEX IF NOT EXISTS idx_sw_industry_l2 ON trade_stock_master(sector_level2);

-- 创建复合索引用于申万行业选股
CREATE INDEX IF NOT EXISTS idx_sw_industry_composite ON trade_stock_master(sector_level1, sector_level2);
