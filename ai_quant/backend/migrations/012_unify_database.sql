-- ============================================================
-- 012_unify_database.sql
-- 将会话管理和后台管理所有表从SQLite迁移到MySQL huahua_trade数据库
-- 统一数据库体系，消除双数据库模式
-- ============================================================;


-- 会话管理表
CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) NOT NULL DEFAULT '新对话',
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(64) PRIMARY KEY,
    conversation_id VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at VARCHAR(64) NOT NULL,
    INDEX idx_messages_conv (conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- API密钥管理表
CREATE TABLE IF NOT EXISTS admin_api_keys (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    key_type VARCHAR(64) NOT NULL,
    cipher_key TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    INDEX idx_admin_api_keys_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- LLM模型配置表
CREATE TABLE IF NOT EXISTS admin_llm_models (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    api_key_ref VARCHAR(64),
    base_url VARCHAR(512),
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    sort_order INT NOT NULL DEFAULT 0,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    INDEX idx_admin_llm_models_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 工具配置表
CREATE TABLE IF NOT EXISTS admin_tools (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL,
    enabled INT NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 智能体配置表
CREATE TABLE IF NOT EXISTS admin_agents (
    id VARCHAR(64) PRIMARY KEY,
    role VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model_id VARCHAR(64),
    skills TEXT NOT NULL,
    tools TEXT NOT NULL,
    prompt_id VARCHAR(64),
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    INDEX idx_admin_agents_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 提示词模板表
CREATE TABLE IF NOT EXISTS admin_prompts (
    id VARCHAR(64) PRIMARY KEY,
    category VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    variables TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    INDEX idx_admin_prompts_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 提示词版本表
CREATE TABLE IF NOT EXISTS admin_prompt_versions (
    id VARCHAR(64) PRIMARY KEY,
    prompt_id VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    version INT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    INDEX idx_admin_prompt_versions_prompt (prompt_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 飞书配置表
CREATE TABLE IF NOT EXISTS admin_feishu_config (
    id VARCHAR(64) PRIMARY KEY,
    app_id VARCHAR(255) NOT NULL DEFAULT '',
    app_secret_cipher TEXT NOT NULL,
    ws_url VARCHAR(512) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'disabled',
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 系统设置表
CREATE TABLE IF NOT EXISTS admin_system_settings (
    id VARCHAR(64) PRIMARY KEY,
    `key` VARCHAR(255) NOT NULL UNIQUE,
    `value` TEXT NOT NULL,
    description TEXT,
    updated_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- AI定时任务表
CREATE TABLE IF NOT EXISTS admin_ai_scheduled_tasks (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    task_type VARCHAR(64) NOT NULL,
    cron_expr VARCHAR(128) NOT NULL,
    model_id VARCHAR(64),
    prompt_id VARCHAR(64),
    enabled INT NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    INDEX idx_admin_ai_scheduled_tasks_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- AI任务执行日志表
CREATE TABLE IF NOT EXISTS admin_ai_task_logs (
    id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    started_at VARCHAR(64) NOT NULL,
    finished_at VARCHAR(64),
    result TEXT,
    error_message TEXT,
    INDEX idx_admin_ai_task_logs_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- AI调用日志表
CREATE TABLE IF NOT EXISTS admin_ai_logs (
    id VARCHAR(64) PRIMARY KEY,
    conversation_id VARCHAR(64),
    session_id VARCHAR(64),
    model_used VARCHAR(255),
    tokens_used INT DEFAULT 0,
    duration_ms INT DEFAULT 0,
    prompt_template TEXT,
    source VARCHAR(64) DEFAULT 'system',
    created_at VARCHAR(64) NOT NULL,
    INDEX idx_admin_ai_logs_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Task-03: 消除JSON+MySQL双写冗余 - 新增表
-- ============================================================

-- 执行任务存储表（替代JSON文件存储）
CREATE TABLE IF NOT EXISTS trade_execution_tasks (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL,
    side VARCHAR(8) NOT NULL,
    total_qty INT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'draft',
    created_at VARCHAR(64) NOT NULL,
    started_at VARCHAR(64),
    finished_at VARCHAR(64),
    error TEXT,
    meta TEXT DEFAULT '{}'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 风控审计日志表（替代JSON文件存储）
CREATE TABLE IF NOT EXISTS trade_risk_audit (
    id VARCHAR(64) PRIMARY KEY,
    timestamp TEXT NOT NULL,
    symbol VARCHAR(16) NOT NULL,
    direction VARCHAR(8) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    price DECIMAL(10,2),
    quantity INT,
    decision VARCHAR(16) NOT NULL,
    rule_name VARCHAR(64) NOT NULL,
    suggested_pct DECIMAL(5,2),
    reason TEXT,
    created_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
