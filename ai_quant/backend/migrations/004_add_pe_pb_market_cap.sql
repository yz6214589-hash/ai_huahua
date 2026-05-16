-- =============================================================================
-- AI 量化投资系统 - 数据库迁移脚本 (V004)
-- 版本: 4.0
-- 创建日期: 2026-05-15
-- 作者: AI 助手
-- 描述: 为 trade_stock_financial 表添加 PE、PB、市值等估值字段
-- =============================================================================

SELECT '====================================' AS '';
SELECT '开始执行数据库迁移 V004' AS '迁移状态';
SELECT '执行时间:' AS '', NOW() AS '';

-- -----------------------------------------------------------------------------
-- 检查字段是否存在
-- -----------------------------------------------------------------------------

SET @_has_pe = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_stock_financial'
      AND column_name = 'pe_ttm'
);

SET @_has_pb = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_stock_financial'
      AND column_name = 'pb'
);

SET @_has_market_cap = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_stock_financial'
      AND column_name = 'market_cap'
);

-- -----------------------------------------------------------------------------
-- 添加估值字段
-- -----------------------------------------------------------------------------

SELECT '添加 PE、PB、市值等估值字段...' AS '执行步骤';

ALTER TABLE `trade_stock_financial`
    ADD COLUMN IF NOT EXISTS `pe_ttm` DECIMAL(12,4) NULL COMMENT '滚动市盈率TTM'
    AFTER `total_equity`;

ALTER TABLE `trade_stock_financial`
    ADD COLUMN IF NOT EXISTS `pb` DECIMAL(10,4) NULL COMMENT '市净率PB'
    AFTER `pe_ttm`;

ALTER TABLE `trade_stock_financial`
    ADD COLUMN IF NOT EXISTS `market_cap` DECIMAL(20,2) NULL COMMENT '总市值（元）'
    AFTER `pb`;

ALTER TABLE `trade_stock_financial`
    ADD COLUMN IF NOT EXISTS `float_market_cap` DECIMAL(20,2) NULL COMMENT '流通市值（元）'
    AFTER `market_cap`;

-- -----------------------------------------------------------------------------
-- 迁移完成校验
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '校验新增字段...' AS '校验阶段';

SELECT 'trade_stock_financial.pe_ttm' AS col, COUNT(*) AS exists_flag
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_stock_financial'
  AND column_name = 'pe_ttm'
UNION ALL
SELECT 'trade_stock_financial.pb', COUNT(*) FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_stock_financial'
  AND column_name = 'pb'
UNION ALL
SELECT 'trade_stock_financial.market_cap', COUNT(*) FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_stock_financial'
  AND column_name = 'market_cap'
UNION ALL
SELECT 'trade_stock_financial.float_market_cap', COUNT(*) FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_stock_financial'
  AND column_name = 'float_market_cap';

SELECT '====================================' AS '';
SELECT '数据库迁移 V004 执行完成' AS '完成状态';
SELECT '完成时间:' AS '', NOW() AS '';
SELECT '====================================' AS '';
