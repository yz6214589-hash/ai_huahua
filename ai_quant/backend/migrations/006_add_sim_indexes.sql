-- =============================================================================
-- AI 量化投资系统 - 数据库索引优化迁移脚本 (V006)
-- 版本: 6.0
-- 创建日期: 2026-05-15
-- 作者: AI 助手
-- 描述: 为模拟盘相关表添加性能优化索引
-- =============================================================================

SELECT '====================================' AS '';
SELECT '开始执行数据库索引优化 V006' AS '迁移状态';
SELECT '执行时间:' AS '', NOW() AS '';

-- -----------------------------------------------------------------------------
-- sim_account 表索引
-- -----------------------------------------------------------------------------

SELECT '优化 sim_account 表索引...' AS '执行步骤';

CREATE INDEX IF NOT EXISTS idx_sim_account_status ON sim_account(status);
CREATE INDEX IF NOT EXISTS idx_sim_account_created_at ON sim_account(created_at);

-- -----------------------------------------------------------------------------
-- sim_position 表索引
-- -----------------------------------------------------------------------------

SELECT '优化 sim_position 表索引...' AS '执行步骤';

CREATE INDEX IF NOT EXISTS idx_sim_position_account_stock ON sim_position(account_id, stock_code);
CREATE INDEX IF NOT EXISTS idx_sim_position_volume ON sim_position(volume);
CREATE INDEX IF NOT EXISTS idx_sim_position_type ON sim_position(position_type);
CREATE INDEX IF NOT EXISTS idx_sim_position_updated ON sim_position(updated_at);

-- -----------------------------------------------------------------------------
-- sim_trade 表索引
-- -----------------------------------------------------------------------------

SELECT '优化 sim_trade 表索引...' AS '执行步骤';

CREATE INDEX IF NOT EXISTS idx_sim_trade_account_time ON sim_trade(account_id, trade_time DESC);
CREATE INDEX IF NOT EXISTS idx_sim_trade_account_side ON sim_trade(account_id, side);
CREATE INDEX IF NOT EXISTS idx_sim_trade_stock ON sim_trade(stock_code, trade_time DESC);
CREATE INDEX IF NOT EXISTS idx_sim_trade_type_time ON sim_trade(account_type, trade_time DESC);

-- -----------------------------------------------------------------------------
-- sim_position_history 表索引
-- -----------------------------------------------------------------------------

SELECT '优化 sim_position_history 表索引...' AS '执行步骤';

CREATE INDEX IF NOT EXISTS idx_sim_history_account_date ON sim_position_history(account_id, record_date DESC);

-- -----------------------------------------------------------------------------
-- 迁移完成校验
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '校验新增索引...' AS '校验阶段';

SELECT 'Indexes for sim_account:' AS '';
SHOW INDEX FROM sim_account;

SELECT 'Indexes for sim_position:' AS '';
SHOW INDEX FROM sim_position;

SELECT 'Indexes for sim_trade:' AS '';
SHOW INDEX FROM sim_trade;

SELECT 'Indexes for sim_position_history:' AS '';
SHOW INDEX FROM sim_position_history;

SELECT '====================================' AS '';
SELECT '数据库索引优化 V006 执行完成' AS '完成状态';
SELECT '完成时间:' AS '', NOW() AS '';
SELECT '====================================' AS '';
