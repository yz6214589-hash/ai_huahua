-- =============================================================================
-- AI 量化投资系统 - 数据库迁移脚本 (V003)
-- 版本: 3.0
-- 创建日期: 2026-05-15
-- 作者: AI 助手
-- 描述: 为 trade_stock_financial 表添加创建时间字段
-- =============================================================================

SELECT '====================================' AS '';
SELECT '开始执行数据库迁移 V003' AS '迁移状态';
SELECT '执行时间:' AS '', NOW() AS '';

-- -----------------------------------------------------------------------------
-- 为 trade_stock_financial 表添加 created_at 字段
-- -----------------------------------------------------------------------------

SET @_has_created_at = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_stock_financial'
      AND column_name = 'created_at'
);

SELECT '为 trade_stock_financial 表添加 created_at 字段...' AS '执行步骤';

ALTER TABLE `trade_stock_financial`
    ADD COLUMN IF NOT EXISTS `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间'
    AFTER `data_source`;

-- -----------------------------------------------------------------------------
-- 迁移完成校验
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '校验新增字段...' AS '校验阶段';

SELECT 'trade_stock_financial.created_at' AS col,
       COUNT(*) AS exists_flag
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'trade_stock_financial'
  AND column_name = 'created_at';

SELECT '====================================' AS '';
SELECT '数据库迁移 V003 执行完成' AS '完成状态';
SELECT '完成时间:' AS '', NOW() AS '';
SELECT '====================================' AS '';
