-- =============================================================================
-- AI 量化投资系统 - 数据库扩展迁移脚本 (V002)
-- 版本: 2.0
-- 适用环境: 开发 / 测试 / 生产
-- 创建日期: 2026-05-12
-- 作者: AI 助手
-- =============================================================================
-- 本脚本新增以下业务模块的数据表：
--   1. 投资晨会工作流（板块指数、晨报、选股、信号）
--   2. 实盘交易闭环（持仓、订单、资金、信号、盈亏）
--   3. 龙头战法（候选池、信号）
--   4. 风控规则与审计增强
--   5. 系统事件日志
--   6. 对话会话管理（MySQL 版本）
--   7. 股票基础信息增强（申万行业分类）
--   8. 日K线增强（板块标签、相位）
-- =============================================================================
-- 使用说明：
--   1. 建议在测试环境先执行验证
--   2. 所有新增表使用 IF NOT EXISTS 确保幂等
--   3. 禁止 DROP 任何已有数据表
--   4. 生产环境执行前请备份数据库
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 第一部分：数据兼容性校验
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '开始执行数据库迁移 V002' AS '迁移状态';
SELECT '执行时间:' AS '', NOW() AS '';

-- 校验 1：确认 trade_stock_master 表存在（前置依赖）
SELECT COUNT(*) AS 'trade_stock_master_exists' FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'trade_stock_master';

-- 校验 2：确认 trade_stock_daily 表存在（前置依赖）
SELECT COUNT(*) AS 'trade_stock_daily_exists' FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'trade_stock_daily';

-- 校验 3：确认数据库字符集
SELECT @@character_set_database AS 'db_charset',
       @@collation_database AS 'db_collation';

-- -----------------------------------------------------------------------------
-- 第二部分：扩展 trade_stock_master 表 - 增加申万行业分类字段
-- -----------------------------------------------------------------------------
-- 说明：原有 trade_stock_master 只有 stock_code/stock_name/source，
--       晨会工作流和龙头战法需要申万一级/二级行业映射关系。
-- -----------------------------------------------------------------------------

SET @_sql = (
    SELECT SQL FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_stock_master'
      AND index_name = 'idx_stock_master_sector2'
    LIMIT 1
);

SET @_has_sector_field = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_stock_master'
      AND column_name = 'sector_level2'
);

SELECT '扩展 trade_stock_master 表（申万行业分类）...' AS '执行步骤';

ALTER TABLE `trade_stock_master`
    ADD COLUMN IF NOT EXISTS `sector_level1` VARCHAR(50) NULL COMMENT '申万一级行业名称'
    AFTER `source`,
    ADD COLUMN IF NOT EXISTS `sector_level2` VARCHAR(50) NULL COMMENT '申万二级行业名称'
    AFTER `sector_level1`,
    ADD COLUMN IF NOT EXISTS `market` VARCHAR(10) NULL COMMENT '所属市场: SH/SZ/BJ/ALL'
    AFTER `sector_level2`,
    ADD COLUMN IF NOT EXISTS `list_date` DATE NULL COMMENT '上市日期'
    AFTER `market`,
    ADD COLUMN IF NOT EXISTS `industry_benchmark` VARCHAR(20) NULL COMMENT '所属行业基准指数代码'
    AFTER `list_date`,
    ADD COLUMN IF NOT EXISTS `is_st` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否ST股: 0-否 1-是'
    AFTER `industry_benchmark`,
    ADD COLUMN IF NOT EXISTS `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '股票状态: active-正常 delisted-退市 suspend-停牌'
    AFTER `is_st`;

-- 新增索引
ALTER TABLE `trade_stock_master`
    ADD INDEX IF NOT EXISTS `idx_stock_master_sector1` (`sector_level1`),
    ADD INDEX IF NOT EXISTS `idx_stock_master_sector2` (`sector_level2`),
    ADD INDEX IF NOT EXISTS `idx_stock_master_market` (`market`),
    ADD INDEX IF NOT EXISTS `idx_stock_master_status` (`status`);

-- -----------------------------------------------------------------------------
-- 第三部分：扩展 trade_stock_daily 表 - 增加板块标签和技术相位
-- -----------------------------------------------------------------------------
-- 说明：支持板块轮动分析中的"静态强度/速度/加速度"三层信号体系计算结果存储。
-- -----------------------------------------------------------------------------

SET @_has_phase_field = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_stock_daily'
      AND column_name = 'sector_phase'
);

SELECT '扩展 trade_stock_daily 表（板块相位、动量因子）...' AS '执行步骤';

ALTER TABLE `trade_stock_daily`
    ADD COLUMN IF NOT EXISTS `sector_level1` VARCHAR(50) NULL COMMENT '所属申万一级行业'
    AFTER `kdj_j`,
    ADD COLUMN IF NOT EXISTS `sector_level2` VARCHAR(50) NULL COMMENT '所属申万二级行业'
    AFTER `sector_level1`,
    ADD COLUMN IF NOT EXISTS `sector_phase` VARCHAR(30) NULL COMMENT '板块相位: accel_up/decel_up/decel_down/accel_down/neutral'
    AFTER `sector_level2`,
    ADD COLUMN IF NOT EXISTS `momentum_1m` DECIMAL(10,4) NULL COMMENT '1个月动量因子（21日累计收益）'
    AFTER `sector_phase`,
    ADD COLUMN IF NOT EXISTS `momentum_3m` DECIMAL(10,4) NULL COMMENT '3个月动量因子（63日累计收益）'
    AFTER `momentum_1m`,
    ADD COLUMN IF NOT EXISTS `momentum_6m` DECIMAL(10,4) NULL COMMENT '6个月动量因子（126日累计收益）'
    AFTER `momentum_3m`,
    ADD COLUMN IF NOT EXISTS `liquidity_score` DECIMAL(10,4) NULL COMMENT '流动性得分（越小越好）'
    AFTER `momentum_6m`,
    ADD COLUMN IF NOT EXISTS `turnover_score` DECIMAL(10,4) NULL COMMENT '换手率得分（越小越好）'
    AFTER `liquidity_score`,
    ADD COLUMN IF NOT EXISTS `volatility_20d` DECIMAL(10,4) NULL COMMENT '20日年化波动率'
    AFTER `turnover_score`,
    ADD COLUMN IF NOT EXISTS `volatility_60d` DECIMAL(10,4) NULL COMMENT '60日年化波动率'
    AFTER `volatility_20d`,
    ADD COLUMN IF NOT EXISTS `alpha_score` DECIMAL(10,4) NULL COMMENT '综合Alpha得分（标准化后）'
    AFTER `volatility_60d`,
    ADD COLUMN IF NOT EXISTS `rank_layer` TINYINT NULL COMMENT '分层排名（1=最优L1组, 5=最差L5组）'
    AFTER `alpha_score`;

-- 新增索引
ALTER TABLE `trade_stock_daily`
    ADD INDEX IF NOT EXISTS `idx_daily_sector1` (`sector_level1`),
    ADD INDEX IF NOT EXISTS `idx_daily_sector2` (`sector_level2`),
    ADD INDEX IF NOT EXISTS `idx_daily_sector_phase` (`sector_phase`),
    ADD INDEX IF NOT EXISTS `idx_daily_alpha_score` (`alpha_score`),
    ADD INDEX IF NOT EXISTS `idx_daily_rank_layer` (`rank_layer`);

-- -----------------------------------------------------------------------------
-- 第四部分：板块日线指数表 trade_sector_daily
-- -----------------------------------------------------------------------------
-- 说明：板块指数非原生，需由成分股合成。
--       支持申万一级（31个）和申万二级（134个）两种粒度。
--       合成方式：累乘法（行业标准），避免停牌/退市导致跳空偏差。
--       指数基准：1000点。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_sector_daily` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `sector_code`           VARCHAR(20) NOT NULL COMMENT '板块代码（如: 801010）',
    `sector_name`           VARCHAR(100) NOT NULL COMMENT '板块名称（如: 医疗服务）',
    `sector_level`          TINYINT NOT NULL DEFAULT 2 COMMENT '行业层级: 1-申万一级 2-申万二级',
    `trade_date`            DATE NOT NULL COMMENT '交易日期',
    `base_value`            DECIMAL(16,4) NOT NULL DEFAULT 1000.0000 COMMENT '基准指数值（统一1000点）',
    `open_idx`              DECIMAL(12,4) NULL COMMENT '开盘指数',
    `high_idx`              DECIMAL(12,4) NULL COMMENT '最高指数',
    `low_idx`               DECIMAL(12,4) NULL COMMENT '最低指数',
    `close_idx`             DECIMAL(12,4) NULL COMMENT '收盘指数',
    `change_pct`            DECIMAL(10,4) NULL COMMENT '涨跌幅(%)',
    `amount`                DECIMAL(20,2) NULL COMMENT '成分股总成交额(元)',
    `component_count`        INT NULL COMMENT '成分股数量',
    `change_count`         INT NULL COMMENT '上涨成分股数量',
    `drop_count`            INT NULL COMMENT '下跌成分股数量',
    `unchanged_count`       INT NULL COMMENT '平盘成分股数量',

    -- 三层信号指标（详见参考文档第3.2节）
    `strength_score`         DECIMAL(10,4) NULL COMMENT '静态强度得分（零阶，速度+RSI+波动率z-score合成）',
    `roc_20`                DECIMAL(10,4) NULL COMMENT '20日涨跌幅(%)，速度代理',
    `ma20_slope`            DECIMAL(10,4) NULL COMMENT 'MA20均线斜率(%)，平滑速度',
    `macd_hist`             DECIMAL(12,6) NULL COMMENT 'MACD柱状图值，二阶加速度代理',
    `macd_delta`            DECIMAL(12,6) NULL COMMENT 'MACD柱状图变化量（加速度变化）',
    `ma20_accel`            DECIMAL(10,4) NULL COMMENT 'MA20斜率变化量（加速度）',
    `phase`                 VARCHAR(30) NULL COMMENT '相位判定: accel_up/decel_up/decel_down/accel_down/neutral',
    `phase_bonus`           DECIMAL(5,2) NULL COMMENT '相位加分（用于综合得分）',
    `composite_score`        DECIMAL(10,4) NULL COMMENT '综合得分（强度+相位加分）',
    `rank_position`         INT NULL COMMENT '当日板块强度排名（1=最强）',

    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_sector_daily` (`sector_code`, `sector_level`, `trade_date`),
    KEY `idx_sector_daily_date` (`trade_date`),
    KEY `idx_sector_daily_level` (`sector_level`),
    KEY `idx_sector_daily_phase` (`phase`),
    KEY `idx_sector_daily_score` (`composite_score`),
    KEY `idx_sector_daily_rank` (`rank_position`),
    KEY `idx_sector_daily_name_date` (`sector_name`, `trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='板块日线指数表（申万一/二级，支持板块轮动分析三层信号）';

-- -----------------------------------------------------------------------------
-- 第五部分：晨会简报主表 trade_morning_brief
-- -----------------------------------------------------------------------------
-- 说明：存储每日晨会简报的元数据，一次晨报包含多个行业排名和股票池。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_morning_brief` (
    `brief_id`              VARCHAR(64) NOT NULL COMMENT '简报唯一ID',
    `brief_date`            DATE NOT NULL COMMENT '简报日期（执行日）',
    `industry_level`        TINYINT NOT NULL DEFAULT 2 COMMENT '行业层级: 1-一级 2-二级',
    `top_n_industries`      INT NOT NULL DEFAULT 5 COMMENT '纳入行业数量',
    `top_n_stocks`          INT NOT NULL DEFAULT 5 COMMENT '每个行业纳入股票数量',
    `lookback_days`         INT NOT NULL DEFAULT 90 COMMENT '数据回看天数',
    `trigger_mode`          VARCHAR(20) NOT NULL DEFAULT 'manual' COMMENT '触发方式: manual-手动 cron-定时 simulate-模拟',
    `status`                VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT '状态: running/success/failed',
    `report_md`             LONGTEXT NULL COMMENT 'Markdown格式晨报全文',
    `report_html`           LONGTEXT NULL COMMENT 'HTML格式晨报全文',
    `run_id`                VARCHAR(64) NULL COMMENT '关联的Agent运行ID',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    `finished_at`            DATETIME NULL,
    `error_message`         TEXT NULL COMMENT '执行失败时的错误信息',
    PRIMARY KEY (`brief_id`),
    UNIQUE KEY `uk_brief_date` (`brief_date`),
    KEY `idx_brief_status` (`status`),
    KEY `idx_brief_date` (`brief_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='晨会简报主表（每日晨报元数据）';

-- -----------------------------------------------------------------------------
-- 第六部分：晨会行业排名 trade_morning_industry
-- -----------------------------------------------------------------------------
-- 说明：存储晨会中各申万二级行业的强度排名、主升浪/反转信号。
--       关联 trade_morning_brief。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_morning_industry` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `brief_id`              VARCHAR(64) NOT NULL COMMENT '所属简报ID',
    `sector_code`           VARCHAR(20) NOT NULL COMMENT '板块代码',
    `sector_name`           VARCHAR(100) NOT NULL COMMENT '板块名称',
    `sector_level`          TINYINT NOT NULL DEFAULT 2 COMMENT '行业层级',
    `rank_position`         INT NOT NULL COMMENT '当日强度排名（1=最强）',
    `rank_change`           INT NULL COMMENT '相对昨日排名变化（正数=上升）',
    `composite_score`        DECIMAL(10,4) NOT NULL COMMENT '综合得分',
    `phase`                 VARCHAR(30) NOT NULL COMMENT '当前相位',
    `phase_bonus`           DECIMAL(5,2) NOT NULL DEFAULT 0.00 COMMENT '相位加分',
    `change_pct`            DECIMAL(10,4) NULL COMMENT '当日涨跌幅(%)',
    `strength`               VARCHAR(50) NULL COMMENT '强度标签: 主升浪/加速/关注/风险/中性',
    `signal_desc`           VARCHAR(255) NULL COMMENT '信号描述（如：光伏，半导体，创新药 关注：风电设备）',
    `win_rate_20d`          DECIMAL(6,2) NULL COMMENT '20日历史胜率(%)',
    `avg_return_20d`        DECIMAL(10,4) NULL COMMENT '20日平均超额收益(%)',
    `blacklist_flag`         TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否黑名单: 0-否 1-是（胜率<30%）',
    `blacklist_reason`       VARCHAR(255) NULL COMMENT '列入黑名单原因',
    `recommendation`        VARCHAR(100) NULL COMMENT '操作建议: 持有/关注/规避/加仓/减仓',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_brief_industry` (`brief_id`, `sector_code`),
    KEY `idx_brief_industry_brief` (`brief_id`),
    KEY `idx_brief_industry_rank` (`rank_position`),
    KEY `idx_brief_industry_phase` (`phase`),
    KEY `idx_brief_industry_blacklist` (`blacklist_flag`),
    CONSTRAINT `fk_brief_industry_brief` FOREIGN KEY (`brief_id`) REFERENCES `trade_morning_brief`(`brief_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='晨会行业排名表（各申万二级行业强度与信号）';

-- -----------------------------------------------------------------------------
-- 第七部分：晨会股票池 trade_morning_stock
-- -----------------------------------------------------------------------------
-- 说明：存储晨会多因子选股结果中选中的股票池及评分。
--       包含个股Alpha得分、所属行业、相位加成、机会类型。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_morning_stock` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `brief_id`              VARCHAR(64) NOT NULL COMMENT '所属简报ID',
    `stock_code`            VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name`            VARCHAR(100) NULL COMMENT '股票名称',
    `sector_code`           VARCHAR(20) NOT NULL COMMENT '所属板块代码',
    `sector_name`           VARCHAR(100) NULL COMMENT '所属板块名称',
    `rank_position`         INT NOT NULL COMMENT '全市场股票池排名（1=最优）',
    `layer`                 TINYINT NOT NULL COMMENT '分层组别（1=L1最优20% ~ 5=L5最差20%）',
    `alpha_score`           DECIMAL(10,4) NOT NULL COMMENT 'Alpha综合得分',
    `opportunity_type`       VARCHAR(20) NOT NULL COMMENT '机会类型: 左侧/右侧/中性',
    `side`                  VARCHAR(10) NOT NULL DEFAULT 'LONG' COMMENT '交易方向: LONG-做多 SHORT-做空',
    `suggestion`            VARCHAR(100) NULL COMMENT '操作建议：买入/持有/观望',
    `target_pct`            DECIMAL(8,2) NULL COMMENT '目标收益率(%)',
    `stop_loss_pct`         DECIMAL(8,2) NULL COMMENT '止损线(%)',
    `holding_period_days`    INT NULL COMMENT '建议持仓周期（天）',
    `confidence`            DECIMAL(5,2) NULL COMMENT '置信度(0-100)',
    `notes`                 TEXT NULL COMMENT '备注说明',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_brief_stock` (`brief_id`, `stock_code`),
    KEY `idx_brief_stock_brief` (`brief_id`),
    KEY `idx_brief_stock_code` (`stock_code`),
    KEY `idx_brief_stock_rank` (`rank_position`),
    KEY `idx_brief_stock_layer` (`layer`),
    KEY `idx_brief_stock_alpha` (`alpha_score` DESC),
    CONSTRAINT `fk_brief_stock_brief` FOREIGN KEY (`brief_id`) REFERENCES `trade_morning_brief`(`brief_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='晨会股票池表（多因子选股结果，L1~L5分层）';

-- -----------------------------------------------------------------------------
-- 第八部分：实盘持仓表 trade_live_position
-- -----------------------------------------------------------------------------
-- 说明：存储当前实盘持仓快照，与 live_state.json 保持同步。
--       支持模拟盘和真实QMT账户。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_live_position` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `account_id`            VARCHAR(32) NOT NULL DEFAULT 'SIM' COMMENT '账户ID: SIM-模拟盘',
    `stock_code`            VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name`            VARCHAR(100) NULL COMMENT '股票名称',
    `direction`              VARCHAR(10) NOT NULL COMMENT '方向: LONG-多仓 SHORT-空仓',
    `quantity`               INT NOT NULL DEFAULT 0 COMMENT '持仓数量（股）',
    `available_quantity`      INT NOT NULL DEFAULT 0 COMMENT '可用数量（不含挂单）',
    `frozen_quantity`        INT NOT NULL DEFAULT 0 COMMENT '冻结数量（挂单中）',
    `avg_cost`              DECIMAL(12,4) NOT NULL DEFAULT 0.0000 COMMENT '持仓成本价',
    `current_price`         DECIMAL(12,4) NULL COMMENT '当前价格',
    `market_value`           DECIMAL(20,4) NULL COMMENT '持仓市值',
    `profit_loss`            DECIMAL(20,4) NULL COMMENT '持仓盈亏金额',
    `profit_loss_pct`        DECIMAL(10,4) NULL COMMENT '持仓盈亏比例(%)',
    `today_profit_loss`      DECIMAL(20,4) NULL COMMENT '当日盈亏金额',
    `today_profit_loss_pct`  DECIMAL(10,4) NULL COMMENT '当日盈亏比例(%)',
    `position_ratio`        DECIMAL(8,4) NULL COMMENT '持仓占总资金比例(%)',
    `stop_loss_price`       DECIMAL(12,4) NULL COMMENT '止损价',
    `target_price`          DECIMAL(12,4) NULL COMMENT '目标价',
    `entry_date`            DATE NULL COMMENT '建仓日期',
    `updated_at`            DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_position_account_stock` (`account_id`, `stock_code`),
    KEY `idx_position_account` (`account_id`),
    KEY `idx_position_stock` (`stock_code`),
    KEY `idx_position_profit_pct` (`profit_loss_pct`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='实盘持仓表（当前持仓快照）';

-- -----------------------------------------------------------------------------
-- 第九部分：实盘订单表 trade_live_order
-- -----------------------------------------------------------------------------
-- 说明：记录每一笔委托/订单，含模拟委托和真实委托。
--       关联 trade_live_position。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_live_order` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `order_id`              VARCHAR(64) NOT NULL COMMENT '订单ID（委托单号）',
    `account_id`            VARCHAR(32) NOT NULL DEFAULT 'SIM' COMMENT '账户ID',
    `stock_code`            VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name`            VARCHAR(100) NULL COMMENT '股票名称',
    `direction`              VARCHAR(10) NOT NULL COMMENT '方向: BUY-买入 SELL-卖出',
    `order_type`            VARCHAR(20) NOT NULL COMMENT '订单类型: MARKET-市价 LIMIT-限价',
    `order_price`           DECIMAL(12,4) NULL COMMENT '委托价格',
    `order_quantity`         INT NOT NULL COMMENT '委托数量',
    `filled_quantity`        INT NOT NULL DEFAULT 0 COMMENT '成交数量',
    `avg_filled_price`      DECIMAL(12,4) NULL COMMENT '平均成交价',
    `order_amount`           DECIMAL(20,4) NULL COMMENT '委托金额（含手续费估算）',
    `filled_amount`         DECIMAL(20,4) NULL COMMENT '成交金额',
    `commission`            DECIMAL(12,4) NULL COMMENT '手续费',
    `status`                VARCHAR(20) NOT NULL COMMENT '状态: pending/partial_filled/filled/cancelled/rejected/failed',
    `signal_source`        VARCHAR(50) NULL COMMENT '信号来源: morning/dragony/dragon_v2/manual',
    `signal_id`             VARCHAR(64) NULL COMMENT '触发信号ID',
    `position_id`           BIGINT NULL COMMENT '关联持仓ID（开仓后）',
    `order_time`            DATETIME NOT NULL COMMENT '委托时间',
    `update_time`           DATETIME NULL COMMENT '最后更新时间',
    `cancel_time`           DATETIME NULL COMMENT '撤单时间',
    `error_message`         TEXT NULL COMMENT '失败/拒绝原因',
    `notes`                 TEXT NULL COMMENT '备注',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_order_id` (`order_id`),
    KEY `idx_order_account` (`account_id`),
    KEY `idx_order_stock` (`stock_code`),
    KEY `idx_order_status` (`status`),
    KEY `idx_order_time` (`order_time`),
    KEY `idx_order_signal` (`signal_source`),
    KEY `idx_order_position` (`position_id`),
    CONSTRAINT `fk_order_position` FOREIGN KEY (`position_id`) REFERENCES `trade_live_position`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='实盘订单表（委托与成交记录）';

-- -----------------------------------------------------------------------------
-- 第十部分：实盘资金账户表 trade_live_capital
-- -----------------------------------------------------------------------------
-- 说明：记录每个账户的可用资金、总资产、冻结资金。
--       每日收盘后快照，支持盈亏历史分析。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_live_capital` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `account_id`            VARCHAR(32) NOT NULL COMMENT '账户ID',
    `account_name`          VARCHAR(100) NOT NULL COMMENT '账户名称',
    `account_type`          VARCHAR(20) NOT NULL DEFAULT 'SIM' COMMENT '账户类型: SIM-模拟盘 LIVE-实盘',
    `init_cash`             DECIMAL(20,4) NOT NULL COMMENT '初始资金',
    `total_asset`           DECIMAL(20,4) NOT NULL COMMENT '总资产（含持仓市值）',
    `cash_balance`          DECIMAL(20,4) NOT NULL COMMENT '可用资金',
    `frozen_cash`           DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '冻结资金（挂单占用）',
    `market_value`          DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '持仓总市值',
    `total_profit_loss`     DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '累计盈亏金额',
    `total_profit_loss_pct` DECIMAL(10,4) NOT NULL DEFAULT 0 COMMENT '累计收益率(%)',
    `today_profit_loss`     DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '当日盈亏金额',
    `today_profit_loss_pct` DECIMAL(10,4) NOT NULL DEFAULT 0 COMMENT '当日收益率(%)',
    `max_drawdown`          DECIMAL(10,4) NULL COMMENT '历史最大回撤(%)',
    `win_rate`              DECIMAL(6,2) NULL COMMENT '历史胜率(%)',
    `total_trades`          INT NOT NULL DEFAULT 0 COMMENT '历史总交易次数',
    `winning_trades`        INT NOT NULL DEFAULT 0 COMMENT '盈利交易次数',
    `circuit_breaker_triggered` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否触发熔断: 0-否 1-是',
    `circuit_breaker_loss_pct` DECIMAL(8,4) NULL COMMENT '熔断触发时的亏损比例(%)',
    `updated_at`            DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_account_id` (`account_id`),
    KEY `idx_capital_type` (`account_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='实盘资金账户表（总资产、盈亏统计）';

-- -----------------------------------------------------------------------------
-- 第十一部分：实盘信号表 trade_live_signal
-- -----------------------------------------------------------------------------
-- 说明：存储由各策略（晨会/龙头/手动）计算出的交易信号。
--       信号经过风控审批后才转为订单。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_live_signal` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `signal_id`             VARCHAR(64) NOT NULL COMMENT '信号唯一ID',
    `account_id`            VARCHAR(32) NOT NULL DEFAULT 'SIM' COMMENT '账户ID',
    `source`                VARCHAR(50) NOT NULL COMMENT '信号来源: morning/dragony/dragon_v2/manual/strategy',
    `stock_code`            VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name`            VARCHAR(100) NULL COMMENT '股票名称',
    `direction`              VARCHAR(10) NOT NULL COMMENT '信号方向: BUY-买入 SELL-卖出',
    `signal_type`            VARCHAR(50) NOT NULL COMMENT '信号类型: open-开仓 close-平仓 stop_loss-止损 take_profit-止盈',
    `strength`              DECIMAL(6,2) NULL COMMENT '信号强度(0-100)',
    `confidence`            DECIMAL(6,2) NULL COMMENT '置信度(0-100)',
    `target_price`          DECIMAL(12,4) NULL COMMENT '建议目标价',
    `stop_loss_price`       DECIMAL(12,4) NULL COMMENT '建议止损价',
    `position_size_pct`     DECIMAL(8,2) NULL COMMENT '建议仓位比例(%)',
    `reason`                TEXT NULL COMMENT '信号原因',
    `entry_condition`        TEXT NULL COMMENT '入场条件描述',
    `phase_context`        VARCHAR(50) NULL COMMENT '当时板块相位上下文',
    `trigger_price`         DECIMAL(12,4) NULL COMMENT '触发价格',
    `status`                VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态: pending/approved/rejected/executed/expired/cancelled',
    `approved_by`           VARCHAR(50) NULL COMMENT '审批人: risk-风控 manual-人工 auto-自动',
    `approved_at`           DATETIME NULL COMMENT '审批时间',
    `reject_reason`         TEXT NULL COMMENT '拒绝原因',
    `executed_order_id`     VARCHAR(64) NULL COMMENT '执行后的订单ID',
    `executed_at`           DATETIME NULL COMMENT '执行时间',
    `expires_at`            DATETIME NULL COMMENT '信号过期时间（超过则失效）',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_signal_id` (`signal_id`),
    KEY `idx_signal_account` (`account_id`),
    KEY `idx_signal_stock` (`stock_code`),
    KEY `idx_signal_source` (`source`),
    KEY `idx_signal_status` (`status`),
    KEY `idx_signal_created` (`created_at`),
    KEY `idx_signal_expires` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='实盘信号表（策略产生的交易信号，待风控审批）';

-- -----------------------------------------------------------------------------
-- 第十二部分：实盘事件日志表 trade_live_event
-- -----------------------------------------------------------------------------
-- 说明：记录主循环（live_loop）执行过程中的所有事件。
--       按严重等级分类：INFO/WARN/CRITICAL/FATAL。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_live_event` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `event_id`              VARCHAR(64) NOT NULL COMMENT '事件唯一ID',
    `account_id`            VARCHAR(32) NOT NULL DEFAULT 'SIM' COMMENT '账户ID',
    `event_level`           VARCHAR(20) NOT NULL COMMENT '事件等级: INFO/WARN/CRITICAL/FATAL',
    `event_type`            VARCHAR(50) NOT NULL COMMENT '事件类型: signal/trade/risk/circuit/health/order/system',
    `source`                VARCHAR(50) NULL COMMENT '事件来源模块',
    `message`               TEXT NOT NULL COMMENT '事件消息',
    `detail`                TEXT NULL COMMENT '事件详情（JSON格式）',
    `stock_code`            VARCHAR(20) NULL COMMENT '关联股票代码',
    `order_id`              VARCHAR(64) NULL COMMENT '关联订单ID',
    `step_name`             VARCHAR(50) NULL COMMENT '主循环步骤名称',
    `aggr_key`              VARCHAR(128) NULL COMMENT '聚合键（INFO级事件30分钟聚合用）',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_event_id` (`event_id`),
    KEY `idx_event_account` (`account_id`),
    KEY `idx_event_level` (`event_level`),
    KEY `idx_event_stock` (`stock_code`),
    KEY `idx_event_order` (`order_id`),
    KEY `idx_event_time` (`created_at`),
    KEY `idx_event_aggr` (`aggr_key`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='实盘事件日志表（五级异常处理事件记录）';

-- -----------------------------------------------------------------------------
-- 第十三部分：实盘盈亏历史表 trade_live_pnl_history
-- -----------------------------------------------------------------------------
-- 说明：每日收盘后记录账户盈亏快照，支持净值曲线和回撤计算。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_live_pnl_history` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `account_id`            VARCHAR(32) NOT NULL COMMENT '账户ID',
    `trade_date`            DATE NOT NULL COMMENT '交易日',
    `total_asset`           DECIMAL(20,4) NOT NULL COMMENT '收盘总资产',
    `cash_balance`          DECIMAL(20,4) NOT NULL COMMENT '收盘可用资金',
    `market_value`          DECIMAL(20,4) NOT NULL COMMENT '收盘持仓市值',
    `today_profit_loss`     DECIMAL(20,4) NOT NULL COMMENT '当日盈亏金额',
    `today_profit_loss_pct` DECIMAL(10,4) NOT NULL COMMENT '当日盈亏比例(%)',
    `cumulative_profit_loss` DECIMAL(20,4) NOT NULL COMMENT '累计盈亏金额',
    `cumulative_profit_loss_pct` DECIMAL(10,4) NOT NULL COMMENT '累计收益率(%)',
    `peak_asset`            DECIMAL(20,4) NOT NULL COMMENT '历史最高资产（用于计算回撤）',
    `drawdown_pct`          DECIMAL(10,4) NOT NULL DEFAULT 0 COMMENT '当前回撤(%)',
    `max_drawdown_pct`      DECIMAL(10,4) NOT NULL DEFAULT 0 COMMENT '历史最大回撤(%)',
    `positions_count`       INT NOT NULL DEFAULT 0 COMMENT '持仓股票数量',
    `trades_count`          INT NOT NULL DEFAULT 0 COMMENT '当日交易次数',
    `winning_trades`        INT NOT NULL DEFAULT 0 COMMENT '当日盈利交易次数',
    `notes`                 TEXT NULL COMMENT '备注',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_pnl_account_date` (`account_id`, `trade_date`),
    KEY `idx_pnl_account` (`account_id`),
    KEY `idx_pnl_date` (`trade_date`),
    KEY `idx_pnl_drawdown` (`drawdown_pct`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='实盘盈亏历史表（每日净值快照）';

-- -----------------------------------------------------------------------------
-- 第十四部分：龙头候选表 trade_dragon_candidate
-- -----------------------------------------------------------------------------
-- 说明：存储每日扫描出的龙头候选股。
--       V1：5大筛选规则（涨幅>5%/排名/市值/量比/过滤ST）。
--       V2：V1+板块共振过滤。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_dragon_candidate` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `scan_date`             DATE NOT NULL COMMENT '扫描日期',
    `version`               VARCHAR(10) NOT NULL COMMENT '版本: V1/V2',
    `stock_code`            VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name`            VARCHAR(100) NOT NULL COMMENT '股票名称',
    `close_price`           DECIMAL(12,4) NOT NULL COMMENT '收盘价',
    `pct_change`            DECIMAL(10,4) NOT NULL COMMENT '涨跌幅(%)',
    `amplitude`             DECIMAL(10,4) NULL COMMENT '振幅(%)',
    `volume_ratio`          DECIMAL(10,4) NULL COMMENT '量比',
    `float_market_cap`      DECIMAL(20,2) NULL COMMENT '流通市值（亿）',
    `turnover_rate`         DECIMAL(10,4) NULL COMMENT '换手率(%)',
    `sector_change_pct`     DECIMAL(10,4) NULL COMMENT '所属板块涨跌幅(%)',
    `sector_rising_ratio`   DECIMAL(6,2) NULL COMMENT '板块上涨家数占比(%)（V2新增）',
    `is_filtered`           TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否被过滤: 0-候选 1-已过滤',
    `filter_reason`         VARCHAR(255) NULL COMMENT '过滤原因（涨停/ST/次新等）',
    `dragon_type`           VARCHAR(50) NULL COMMENT '龙头类型: gap_and_go/follow/breakout/none',
    `score`                 DECIMAL(6,2) NULL COMMENT '综合评分(0-100)',
    `added_to_watch`        TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否加入监控池',
    `added_at`              DATETIME NULL COMMENT '加入监控池时间',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dragon_candidate` (`scan_date`, `version`, `stock_code`),
    KEY `idx_dragon_scan` (`scan_date`),
    KEY `idx_dragon_version` (`version`),
    KEY `idx_dragon_code` (`stock_code`),
    KEY `idx_dragon_pct` (`pct_change` DESC),
    KEY `idx_dragon_score` (`score` DESC),
    KEY `idx_dragon_watch` (`added_to_watch`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='龙头候选表（V1/V2每日扫描结果）';

-- -----------------------------------------------------------------------------
-- 第十五部分：龙头信号表 trade_dragon_signal
-- -----------------------------------------------------------------------------
-- 说明：存储龙头战法产生的具体买卖信号，与 trade_live_signal 关联。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_dragon_signal` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `signal_id`             VARCHAR(64) NOT NULL COMMENT '信号ID',
    `candidate_id`          BIGINT NULL COMMENT '关联龙头候选ID',
    `account_id`            VARCHAR(32) NOT NULL DEFAULT 'SIM' COMMENT '账户ID',
    `stock_code`            VARCHAR(20) NOT NULL COMMENT '股票代码',
    `stock_name`            VARCHAR(100) NULL COMMENT '股票名称',
    `direction`              VARCHAR(10) NOT NULL COMMENT '方向: BUY-买入 SELL-卖出',
    `version`               VARCHAR(10) NOT NULL COMMENT '版本: V1/V2',
    `entry_price`           DECIMAL(12,4) NOT NULL COMMENT '入场价格',
    `target_price`          DECIMAL(12,4) NULL COMMENT '目标价',
    `stop_loss_price`       DECIMAL(12,4) NULL COMMENT '止损价',
    `position_pct`          DECIMAL(8,2) NULL COMMENT '仓位比例(%)',
    `holding_days`          INT NOT NULL DEFAULT 3 COMMENT '目标持仓天数',
    `status`                VARCHAR(20) NOT NULL DEFAULT 'watching' COMMENT '状态: watching-监控中 triggered-已触发 executed-已执行 stopped-已止损 exited-已退出 expired-已过期',
    `entry_trigger_price`   DECIMAL(12,4) NULL COMMENT '触发入场价格',
    `entry_trigger_at`      DATETIME NULL COMMENT '触发时间',
    `exit_price`            DECIMAL(12,4) NULL COMMENT '出场价格',
    `exit_reason`           VARCHAR(50) NULL COMMENT '出场原因: stop_loss/take_profit/time_limit/manual',
    `exit_at`               DATETIME NULL COMMENT '出场时间',
    `profit_loss_pct`       DECIMAL(10,4) NULL COMMENT '收益率(%)',
    `notes`                 TEXT NULL COMMENT '备注',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dragon_signal_id` (`signal_id`),
    KEY `idx_dragon_sig_candidate` (`candidate_id`),
    KEY `idx_dragon_sig_account` (`account_id`),
    KEY `idx_dragon_sig_stock` (`stock_code`),
    KEY `idx_dragon_sig_status` (`status`),
    KEY `idx_dragon_sig_created` (`created_at`),
    CONSTRAINT `fk_dragon_candidate` FOREIGN KEY (`candidate_id`) REFERENCES `trade_dragon_candidate`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='龙头信号表（买卖信号与跟踪记录）';

-- -----------------------------------------------------------------------------
-- 第十六部分：风控规则表 trade_risk_rule
-- -----------------------------------------------------------------------------
-- 说明：存储可配置的风控规则。
--       规则分两类：仓位风控（position）/ 账户风控（account）。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_risk_rule` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `rule_code`             VARCHAR(64) NOT NULL COMMENT '规则代码',
    `rule_name`             VARCHAR(100) NOT NULL COMMENT '规则名称',
    `rule_type`             VARCHAR(20) NOT NULL COMMENT '规则类型: position-仓位 account-账户 global-全局',
    `decision`              VARCHAR(20) NOT NULL COMMENT '触发决策: APPROVE/WARN/REJECT',
    `condition_expr`        TEXT NOT NULL COMMENT '条件表达式（如: position_ratio > 20）',
    `condition_desc`        VARCHAR(255) NULL COMMENT '条件中文描述',
    `max_position_pct`     DECIMAL(8,2) NULL COMMENT '最大持仓比例(%)',
    `max_single_loss_pct`   DECIMAL(8,2) NULL COMMENT '单笔最大亏损(%)',
    `max_daily_loss_pct`    DECIMAL(8,2) NULL COMMENT '当日最大亏损(%)',
    `max_concentration_pct` DECIMAL(8,2) NULL COMMENT '单股最大集中度(%)',
    `min_cash_reserve_pct`  DECIMAL(8,2) NULL COMMENT '最低现金储备比例(%)',
    `circuit_breaker_pct`   DECIMAL(8,2) NULL COMMENT '熔断亏损阈值(%)',
    `priority`              INT NOT NULL DEFAULT 100 COMMENT '规则优先级（数字越小越先执行）',
    `enabled`                TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用: 0-禁用 1-启用',
    `account_id`            VARCHAR(32) NULL COMMENT '适用账户（NULL=全部账户）',
    `notes`                 TEXT NULL COMMENT '备注说明',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at`            DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_rule_code` (`rule_code`),
    KEY `idx_rule_type` (`rule_type`),
    KEY `idx_rule_enabled` (`enabled`),
    KEY `idx_rule_account` (`account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='风控规则表（可配置的风控检查规则）';

-- -----------------------------------------------------------------------------
-- 第十七部分：系统事件日志表 trade_system_event
-- -----------------------------------------------------------------------------
-- 说明：通用系统事件日志，覆盖所有非交易事件的告警与操作记录。
--       与 trade_live_event 的区别：trade_live_event 仅记录交易账户事件。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_system_event` (
    `id`                    BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `event_id`              VARCHAR(64) NOT NULL COMMENT '事件唯一ID',
    `event_level`           VARCHAR(20) NOT NULL COMMENT '事件等级: DEBUG/INFO/WARN/ERROR/CRITICAL',
    `event_module`          VARCHAR(50) NOT NULL COMMENT '模块: agent/jobs/reports/sentiment/risk/morning/dragon/strategy/system',
    `event_type`            VARCHAR(50) NOT NULL COMMENT '事件类型',
    `message`               TEXT NOT NULL COMMENT '事件消息',
    `detail`                TEXT NULL COMMENT '详细信息（JSON）',
    `user_id`               VARCHAR(64) NULL COMMENT '操作用户ID（若有）',
    `ip_address`            VARCHAR(45) NULL COMMENT '请求来源IP',
    `related_id`            VARCHAR(64) NULL COMMENT '关联实体ID（如任务ID、报告ID等）',
    `duration_ms`           BIGINT NULL COMMENT '操作耗时（毫秒）',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_system_event_id` (`event_id`),
    KEY `idx_sys_event_level` (`event_level`),
    KEY `idx_sys_event_module` (`event_module`),
    KEY `idx_sys_event_type` (`event_type`),
    KEY `idx_sys_event_related` (`related_id`),
    KEY `idx_sys_event_time` (`created_at`),
    KEY `idx_sys_event_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='系统事件日志表（通用告警与操作记录）';

-- -----------------------------------------------------------------------------
-- 第十八部分：对话会话管理表 trade_conversation
-- -----------------------------------------------------------------------------
-- 说明：MySQL版本的会话管理表，与现有 SQLite 版本结构一致。
--       支持多对话、新建、切换、删除。
--       如已有 SQLite 版本在生产使用，可通过数据迁移工具同步。
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `trade_conversation` (
    `id`                    VARCHAR(64) NOT NULL COMMENT '会话ID（UUID hex）',
    `title`                 VARCHAR(255) NOT NULL DEFAULT '新对话' COMMENT '会话标题',
    `account_id`            VARCHAR(32) NULL COMMENT '关联账户ID（可选）',
    `status`                VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '状态: active-活跃 archived-已归档 deleted-已删除',
    `message_count`         INT NOT NULL DEFAULT 0 COMMENT '消息数量',
    `last_message_at`       DATETIME NULL COMMENT '最后消息时间',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at`            DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_conv_account` (`account_id`),
    KEY `idx_conv_status` (`status`),
    KEY `idx_conv_updated` (`updated_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='对话会话主表';

CREATE TABLE IF NOT EXISTS `trade_message` (
    `id`                    VARCHAR(64) NOT NULL COMMENT '消息ID',
    `conversation_id`       VARCHAR(64) NOT NULL COMMENT '所属会话ID',
    `role`                  VARCHAR(20) NOT NULL COMMENT '角色: user/assistant/system',
    `content`               TEXT NOT NULL COMMENT '消息内容',
    `metadata`              JSON NULL COMMENT '元数据（如工具调用结果、事件列表等）',
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_msg_conv` (`conversation_id`),
    KEY `idx_msg_created` (`created_at`),
    CONSTRAINT `fk_msg_conv` FOREIGN KEY (`conversation_id`) REFERENCES `trade_conversation`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='对话消息表';

-- -----------------------------------------------------------------------------
-- 第十九部分：增强 trade_stock_financial 表字段
-- -----------------------------------------------------------------------------

SET @_has_roe_field = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_stock_financial'
      AND column_name = 'roe'
);

ALTER TABLE `trade_stock_financial`
    ADD COLUMN IF NOT EXISTS `roe` DECIMAL(10,4) NULL COMMENT '净资产收益率(ROE)(%)'
    AFTER `eps',
    ADD COLUMN IF NOT EXISTS `revenue_growth_yoy` DECIMAL(12,4) NULL COMMENT '营收同比增速(%)'
    AFTER `roe`,
    ADD COLUMN IF NOT EXISTS `profit_growth_yoy` DECIMAL(12,4) NULL COMMENT '净利润同比增速(%)'
    AFTER `revenue_growth_yoy`,
    ADD COLUMN IF NOT EXISTS `gross_margin` DECIMAL(10,4) NULL COMMENT '毛利率(%)'
    AFTER `profit_growth_yoy`,
    ADD COLUMN IF NOT EXISTS `net_margin` DECIMAL(10,4) NULL COMMENT '净利率(%)'
    AFTER `gross_margin`,
    ADD COLUMN IF NOT EXISTS `cash_flow_ratio` DECIMAL(12,4) NULL COMMENT '经营活动现金流比率(%)'
    AFTER `net_margin`,
    ADD COLUMN IF NOT EXISTS `debt_to_asset` DECIMAL(10,4) NULL COMMENT '资产负债率(%)'
    AFTER `cash_flow_ratio`,
    ADD COLUMN IF NOT EXISTS `pe_ttm` DECIMAL(12,4) NULL COMMENT '滚动市盈率TTM'
    AFTER `debt_to_asset`,
    ADD COLUMN IF NOT EXISTS `pb` DECIMAL(10,4) NULL COMMENT '市净率PB'
    AFTER `pe_ttm`,
    ADD COLUMN IF NOT EXISTS `psr` DECIMAL(10,4) NULL COMMENT '市销率PSR'
    AFTER `pb`;

-- -----------------------------------------------------------------------------
-- 第二十部分：增强 trade_sentiment_news 表字段（AI分析结果）
-- -----------------------------------------------------------------------------

SET @_has_sentiment_score_field = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_sentiment_news'
      AND column_name = 'ai_sentiment_score'
);

ALTER TABLE `trade_sentiment_news`
    ADD COLUMN IF NOT EXISTS `ai_sentiment_score` DECIMAL(5,2) NULL COMMENT 'AI情感分析得分(-100~100, 正=多'
    AFTER `market_impact`,
    ADD COLUMN IF NOT EXISTS `ai_keywords` JSON NULL COMMENT 'AI提取关键词列表'
    AFTER `ai_sentiment_score`,
    ADD COLUMN IF NOT EXISTS `ai_summary` TEXT NULL COMMENT 'AI生成摘要'
    AFTER `ai_keywords`,
    ADD COLUMN IF NOT EXISTS `relevance_score` DECIMAL(5,2) NULL COMMENT '与股票的关联度得分(0~100)'
    AFTER `ai_summary`,
    ADD COLUMN IF NOT EXISTS `event_impact` VARCHAR(20) NULL COMMENT '事件影响: positive/negative/neutral'
    AFTER `relevance_score`,
    ADD COLUMN IF NOT EXISTS `urgency_level` VARCHAR(10) NULL COMMENT '紧急程度: high/medium/low'
    AFTER `event_impact`;

-- -----------------------------------------------------------------------------
-- 第二十一部分：增强 trade_calendar_event 表字段（AI分析）
-- -----------------------------------------------------------------------------

SET @_has_ai_impact_field = (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'trade_calendar_event'
      AND column_name = 'ai_impact_predicted'
);

ALTER TABLE `trade_calendar_event`
    ADD COLUMN IF NOT EXISTS `ai_impact_predicted` VARCHAR(50) NULL COMMENT 'AI预测影响: bull/bear/neutral'
    AFTER `impact`,
    ADD COLUMN IF NOT EXISTS `ai_confidence` DECIMAL(5,2) NULL COMMENT 'AI置信度(0~100)'
    AFTER `ai_impact_predicted`,
    ADD COLUMN IF NOT EXISTS `ai_relevance_china` DECIMAL(5,2) NULL COMMENT '对中国市场相关性(0~100)'
    AFTER `ai_confidence`,
    ADD COLUMN IF NOT EXISTS `previous_release_date` DATE NULL COMMENT '前值发布日期'
    AFTER `actual_value`,
    ADD COLUMN IF NOT EXISTS `consensus_forecast` VARCHAR(50) NULL COMMENT '市场共识预测值'
    AFTER `previous_release_date`;

-- -----------------------------------------------------------------------------
-- 第二十二部分：索引优化 - 为高频查询添加复合索引
-- -----------------------------------------------------------------------------

ALTER TABLE `trade_stock_daily`
    ADD INDEX IF NOT EXISTS `idx_daily_code_date_close` (`stock_code`, `trade_date`, `close_price`);

ALTER TABLE `trade_stock_daily`
    ADD INDEX IF NOT EXISTS `idx_daily_date_phase` (`trade_date`, `sector_phase`);

ALTER TABLE `trade_stock_daily`
    ADD INDEX IF NOT EXISTS `idx_daily_date_rank` (`trade_date`, `rank_layer`);

ALTER TABLE `trade_sentiment_news`
    ADD INDEX IF NOT EXISTS `idx_sentiment_news_code_score` (`stock_code`, `ai_sentiment_score`);

ALTER TABLE `trade_sentiment_event`
    ADD INDEX IF NOT EXISTS `idx_sentiment_evt_signal` (`signal_action`);

ALTER TABLE `trade_live_position`
    ADD INDEX IF NOT EXISTS `idx_position_account_pl` (`account_id`, `profit_loss_pct` DESC);

ALTER TABLE `trade_live_capital`
    ADD INDEX IF NOT EXISTS `idx_capital_drawdown` (`max_drawdown` DESC);

-- -----------------------------------------------------------------------------
-- 第二十三部分：迁移完成校验
-- -----------------------------------------------------------------------------

SELECT '====================================' AS '';
SELECT '迁移执行完成，开始结果校验' AS '校验阶段';

-- 校验新增表是否存在
SELECT 'trade_sector_daily' AS tbl, COUNT(*) AS cnt FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_sector_daily'
UNION ALL
SELECT 'trade_morning_brief', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_morning_brief'
UNION ALL
SELECT 'trade_morning_industry', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_morning_industry'
UNION ALL
SELECT 'trade_morning_stock', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_morning_stock'
UNION ALL
SELECT 'trade_live_position', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_live_position'
UNION ALL
SELECT 'trade_live_order', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_live_order'
UNION ALL
SELECT 'trade_live_capital', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_live_capital'
UNION ALL
SELECT 'trade_live_signal', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_live_signal'
UNION ALL
SELECT 'trade_live_event', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_live_event'
UNION ALL
SELECT 'trade_live_pnl_history', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_live_pnl_history'
UNION ALL
SELECT 'trade_dragon_candidate', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_dragon_candidate'
UNION ALL
SELECT 'trade_dragon_signal', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_dragon_signal'
UNION ALL
SELECT 'trade_risk_rule', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_risk_rule'
UNION ALL
SELECT 'trade_system_event', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_system_event'
UNION ALL
SELECT 'trade_conversation', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_conversation'
UNION ALL
SELECT 'trade_message', COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'trade_message';

-- 校验新增字段
SELECT 'trade_stock_master.sector_level2' AS col,
       COUNT(*) AS exists_flag
FROM information_schema.columns
WHERE table_schema = DATABASE() AND table_name = 'trade_stock_master' AND column_name = 'sector_level2'
UNION ALL
SELECT 'trade_stock_daily.sector_phase',
       COUNT(*) FROM information_schema.columns
       WHERE table_schema = DATABASE() AND table_name = 'trade_stock_daily' AND column_name = 'sector_phase'
UNION ALL
SELECT 'trade_stock_daily.momentum_1m',
       COUNT(*) FROM information_schema.columns
       WHERE table_schema = DATABASE() AND table_name = 'trade_stock_daily' AND column_name = 'momentum_1m'
UNION ALL
SELECT 'trade_stock_daily.alpha_score',
       COUNT(*) FROM information_schema.columns
       WHERE table_schema = DATABASE() AND table_name = 'trade_stock_daily' AND column_name = 'alpha_score'
UNION ALL
SELECT 'trade_live_position.profit_loss_pct',
       COUNT(*) FROM information_schema.columns
       WHERE table_schema = DATABASE() AND table_name = 'trade_live_position' AND column_name = 'profit_loss_pct';

SELECT '====================================' AS '';
SELECT '数据库迁移 V002 执行完成' AS '完成状态';
SELECT '完成时间:' AS '', NOW() AS '';
SELECT '====================================' AS '';
