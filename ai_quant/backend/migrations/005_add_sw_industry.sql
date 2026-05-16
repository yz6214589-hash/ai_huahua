-- =============================================================================
-- AI 量化投资系统 - 数据库迁移脚本 (V005)
-- 版本: 5.0
-- 创建日期: 2026-05-15
-- 作者: AI 助手
-- 描述: 为 trade_stock_info 表添加申万行业分类字段
-- 参考: CASE-A-板块数据准备 的表结构
-- =============================================================================

SELECT '====================================' AS '';
SELECT '开始执行数据库迁移 V005' AS '迁移状态';
SELECT '执行时间:' AS '', NOW() AS '';

-- -----------------------------------------------------------------------------
-- 添加申万行业分类字段
-- -----------------------------------------------------------------------------

SELECT '添加申万行业分类字段...' AS '执行步骤';

-- sector_level1: 申万一级行业（31个）
ALTER TABLE `trade_stock_info`
    ADD COLUMN IF NOT EXISTS `sector_level1` VARCHAR(50) NULL COMMENT '申万一级行业'
    AFTER `industry`;

-- sector_level2: 申万二级行业（131个）
ALTER TABLE `trade_stock_info`
    ADD COLUMN IF NOT EXISTS `sector_level2` VARCHAR(50) NULL COMMENT '申万二级行业'
    AFTER `sector_level1`;

-- sector_level3: 申万三级行业（336个）
ALTER TABLE `trade_stock_info`
    ADD COLUMN IF NOT EXISTS `sector_level3` VARCHAR(50) NULL COMMENT '申万三级行业'
    AFTER `sector_level2`;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_sector_level1 ON `trade_stock_info`(`sector_level1`);
CREATE INDEX IF NOT EXISTS idx_sector_level2 ON `trade_stock_info`(`sector_level2`);
CREATE INDEX IF NOT EXISTS idx_sector_level3 ON `trade_stock_info`(`sector_level3`);

-- -----------------------------------------------------------------------------
-- 迁移完成校验
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '校验新增字段...' AS '校验阶段';

SELECT 'trade_stock_info.sector_level1' AS col, COUNT(*) AS exists_flag
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_stock_info'
  AND column_name = 'sector_level1'
UNION ALL
SELECT 'trade_stock_info.sector_level2', COUNT(*) FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_stock_info'
  AND column_name = 'sector_level2'
UNION ALL
SELECT 'trade_stock_info.sector_level3', COUNT(*) FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_stock_info'
  AND column_name = 'sector_level3';

SELECT '====================================' AS '';
SELECT '数据库迁移 V005 执行完成' AS '完成状态';
SELECT '完成时间:' AS '', NOW() AS '';
SELECT '====================================' AS '';
