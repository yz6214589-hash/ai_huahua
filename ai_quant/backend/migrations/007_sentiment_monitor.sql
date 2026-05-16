-- 舆情监控定时任务模块数据库表结构

-- 舆情监控定时任务配置表
CREATE TABLE IF NOT EXISTS sentiment_schedule (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    name VARCHAR(100) NOT NULL COMMENT '任务名称',
    enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用：0-停用，1-启用',
    schedule_type VARCHAR(20) NOT NULL COMMENT '调度类型：market_open-开盘时段，daily-每日定时',
    cron_expression VARCHAR(64) NOT NULL COMMENT 'Cron表达式',
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai' COMMENT '时区',
    frequency VARCHAR(20) COMMENT '执行频率：hourly-每小时，every_2_hours-每2小时，every_4_hours-每4小时，custom-自定义',
    custom_minutes INT COMMENT '自定义执行间隔（分钟）',
    use_watchlist TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否使用自选股：0-否，1-是',
    use_llm TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否启用LLM精检：0-否，1-是',
    days_back INT NOT NULL DEFAULT 3 COMMENT '查询历史天数',
    notification_enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用通知：0-否，1-是',
    notification_threshold FLOAT COMMENT '通知阈值（情感得分低于此值时通知）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_schedule_enabled (enabled),
    INDEX idx_schedule_type (schedule_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='舆情监控定时任务配置表';

-- 舆情监控运行记录表
CREATE TABLE IF NOT EXISTS sentiment_run (
    run_id VARCHAR(32) PRIMARY KEY COMMENT '运行ID',
    schedule_id INT COMMENT '关联的定时任务ID',
    trigger_type VARCHAR(16) NOT NULL COMMENT '触发类型：scheduled-定时触发，manual-手动触发',
    stock_codes_json TEXT NOT NULL COMMENT '监控股票代码JSON数组',
    stock_names_json TEXT COMMENT '监控股票名称JSON数组',
    days INT NOT NULL DEFAULT 3 COMMENT '查询历史天数',
    use_llm TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否启用LLM精检',
    status VARCHAR(16) NOT NULL COMMENT '状态：waiting-等待，running-运行中，success-成功，failed-失败',
    total_events INT NOT NULL DEFAULT 0 COMMENT '检测到的事件总数',
    total_news INT NOT NULL DEFAULT 0 COMMENT '抓取到的新闻总数',
    positive_count INT NOT NULL DEFAULT 0 COMMENT '正面舆情数量',
    negative_count INT NOT NULL DEFAULT 0 COMMENT '负面舆情数量',
    neutral_count INT NOT NULL DEFAULT 0 COMMENT '中性舆情数量',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    started_at DATETIME COMMENT '开始时间',
    finished_at DATETIME COMMENT '完成时间',
    error_message TEXT COMMENT '错误信息',
    INDEX idx_run_created (created_at),
    INDEX idx_run_status (status),
    INDEX idx_run_schedule (schedule_id),
    FOREIGN KEY (schedule_id) REFERENCES sentiment_schedule(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='舆情监控运行记录表';

-- 舆情新闻表
CREATE TABLE IF NOT EXISTS sentiment_news (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    run_id VARCHAR(32) NOT NULL COMMENT '关联的运行ID',
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(100) COMMENT '股票名称',
    source_type VARCHAR(16) NOT NULL COMMENT '来源类型：news-新闻，notice-公告',
    title VARCHAR(255) COMMENT '新闻标题',
    url TEXT COMMENT '原文链接',
    published_at DATETIME COMMENT '发布时间',
    content LONGTEXT COMMENT '正文内容',
    sentiment VARCHAR(16) COMMENT '情感分类：positive-正面，negative-负面，neutral-中性',
    sentiment_score INT COMMENT '情感得分 1-5',
    summary TEXT COMMENT '摘要',
    market_impact TEXT COMMENT '市场影响',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_news_run (run_id),
    INDEX idx_news_stock (stock_code),
    INDEX idx_news_sentiment (sentiment),
    INDEX idx_news_published (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='舆情新闻表';

-- 舆情事件表
CREATE TABLE IF NOT EXISTS sentiment_event (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    run_id VARCHAR(32) NOT NULL COMMENT '关联的运行ID',
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(100) COMMENT '股票名称',
    source_type VARCHAR(16) NOT NULL COMMENT '来源类型',
    source_title VARCHAR(255) COMMENT '来源标题',
    source_url TEXT COMMENT '来源链接',
    published_at DATETIME COMMENT '发布时间',
    event_type VARCHAR(16) NOT NULL COMMENT '事件类型：positive-利好，negative-利空，policy-政策',
    event_category VARCHAR(64) NOT NULL COMMENT '事件类别',
    signal_action VARCHAR(32) NOT NULL COMMENT '策略建议',
    signal_reason VARCHAR(255) COMMENT '信号原因',
    impact VARCHAR(255) COMMENT '影响说明',
    confidence INT DEFAULT 3 COMMENT '置信度 1-5',
    urgency VARCHAR(8) DEFAULT '中' COMMENT '紧急度：高/中/低',
    sentiment_score INT COMMENT '情感得分',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_event_run (run_id),
    INDEX idx_event_stock (stock_code),
    INDEX idx_event_type (event_type),
    INDEX idx_event_urgency (urgency),
    INDEX idx_event_published (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='舆情事件表';

-- 自定义股票监控列表
CREATE TABLE IF NOT EXISTS sentiment_stock_list (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(100) COMMENT '股票名称',
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '添加时间',
    notes TEXT COMMENT '备注',
    UNIQUE KEY uk_stock_code (stock_code),
    INDEX idx_stock_list_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自定义股票监控列表';

-- 插入默认定时任务配置
INSERT INTO sentiment_schedule (name, enabled, schedule_type, cron_expression, frequency, use_watchlist, days, notification_enabled)
VALUES
    ('每日收盘后舆情扫描', 1, 'market_open', '10 15 * * 1-5', 'custom', 1, 3, 1),
    ('上午10点舆情检查', 0, 'market_open', '0 10 * * 1-5', 'custom', 1, 1, 1),
    ('下午14点舆情检查', 0, 'market_open', '0 14 * * 1-5', 'custom', 1, 1, 1)
ON DUPLICATE KEY UPDATE name = VALUES(name);
