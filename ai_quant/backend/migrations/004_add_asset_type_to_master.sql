-- =============================================================================
-- AI 量化投资系统 - 数据库迁移脚本 (V004)
-- 新增：trade_stock_master 添加 asset_type 字段
-- 用途：区分个股（stock）和指数（index），统一管理所有资产类型
-- =============================================================================

SELECT '====================================' AS '';
SELECT '开始执行数据库迁移 V004' AS '迁移状态';
SELECT '执行时间:' AS '', NOW() AS '';

-- ---------------------------------------------------------------------------
-- 1. 给 trade_stock_master 表添加 asset_type 字段
-- ---------------------------------------------------------------------------
-- 说明：该字段用于区分每笔记录是真实个股还是指数代码。
--       个股对应真实的 A 股上市公司，指数对应沪深交易所主要指数。
--       默认值为 'stock'，不影响现有查询逻辑。
-- ---------------------------------------------------------------------------

ALTER TABLE `trade_stock_master`
ADD COLUMN `asset_type` VARCHAR(10) NOT NULL DEFAULT 'stock'
COMMENT '资产类型: stock-个股 index-指数'
AFTER `stock_code`;

-- 添加查询索引
ALTER TABLE `trade_stock_master`
ADD INDEX `idx_master_asset_type` (`asset_type`);

-- ---------------------------------------------------------------------------
-- 2. 更新已存在的指数记录（规则驱动更新，与 index_data.py 中的 INDEX_META 同步）
-- ---------------------------------------------------------------------------
-- 上证指数系列（000xxx.SH）
UPDATE `trade_stock_master`
SET `asset_type` = 'index'
WHERE `asset_type` = 'stock'
AND `stock_code` REGEXP '^000[0-9]{3}\\.SH$';

-- 深证指数系列（399xxx.SZ）
UPDATE `trade_stock_master`
SET `asset_type` = 'index'
WHERE `asset_type` = 'stock'
AND `stock_code` REGEXP '^399[0-9]{3}\\.SZ$';

-- 科创50（000688.SH）已在上述规则中覆盖
-- 剩余名称含"指数"的代码
UPDATE `trade_stock_master`
SET `asset_type` = 'index'
WHERE `asset_type` = 'stock'
AND (`stock_name` LIKE '%指数%'
     OR `stock_name` LIKE '%综指%'
     OR `stock_name` LIKE '%成指%');

-- ---------------------------------------------------------------------------
-- 3. 统计更新结果
-- ---------------------------------------------------------------------------

SELECT 'asset_type=stock' AS asst, COUNT(*) AS cnt FROM trade_stock_master WHERE asset_type = 'stock'
UNION ALL
SELECT 'asset_type=index' AS asst, COUNT(*) AS cnt FROM trade_stock_master WHERE asset_type = 'index';

SELECT '====================================' AS '';
SELECT '数据库迁移 V004 执行完成，请继续执行 Python 补充脚本添加缺失的指数代码' AS '提示';
SELECT '完成时间:' AS '', NOW() AS '';
SELECT '====================================' AS '';
