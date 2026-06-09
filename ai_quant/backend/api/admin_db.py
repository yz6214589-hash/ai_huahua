"""
管理后台数据库初始化模块

负责创建和管理后台管理系统的所有数据库表结构，包括：
- API密钥管理
- LLM模型配置
- 工具配置
- 智能体配置
- 提示词模板
- 飞书配置
- 系统配置
- AI定时任务及日志
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

_DB_DIR = Path(__file__).resolve().parent.parent / ".data"
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DB_DIR / "admin.db"

_lock = threading.Lock()


def get_admin_db() -> tuple[sqlite3.Connection, threading.Lock]:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn, _lock


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seed_default_data(conn: sqlite3.Connection):
    cur = conn.cursor()

    # 默认飞书配置
    cur.execute(
        "SELECT COUNT(*) FROM admin_feishu_config"
    )
    if cur.fetchone()[0] == 0:
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO admin_feishu_config (id, app_id, app_secret_cipher, ws_url, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, "", "", "wss://open.feishu.cn/event", "disabled", now, now),
        )

    # 默认系统设置
    default_settings = [
        ("app_name", "AI 投资助手", "应用名称"),
        ("app_version", "1.0.0", "应用版本号"),
        ("log_dir", ".ai_quant/logs", "日志文件目录"),
        ("log_level", "INFO", "日志级别"),
        ("log_retention_days", "30", "日志保留天数"),
        ("admin_session_timeout", "3600", "管理后台会话超时时间（秒）"),
    ]
    for key, value, description in default_settings:
        cur.execute(
            "SELECT COUNT(*) FROM admin_system_settings WHERE key = ?", (key,)
        )
        if cur.fetchone()[0] == 0:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO admin_system_settings (id, key, value, description, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, key, value, description, now),
            )

    # 默认智能体
    default_agents = [
        ("charles", "Charles", "数据分析师，负责数据查询、股票筛选、技术分析",
         "擅长使用各种数据工具进行量化分析", "data_analysis"),
        ("zoe", "Zoe", "行业研究员，负责基本面分析、财务分析、行业研究",
         "擅长基本面分析和行业研究", "financial_analysis"),
        ("kris", "Kris", "风控专家，负责风险评估、仓位管理、止损策略",
         "擅长风险控制和资金管理", "risk_management"),
        ("ethan", "Ethan", "交易员，负责策略执行、订单管理、交易复盘",
         "擅长策略执行和交易管理", "trading"),
        ("ceo", "CEO", "投资决策官，负责整体策略制定、团队协调、投资决策",
         "负责整体投资决策和团队管理", "decision_making"),
    ]
    for role, name, description, agent_desc, _ in default_agents:
        cur.execute(
            "SELECT COUNT(*) FROM admin_agents WHERE role = ?", (role,)
        )
        if cur.fetchone()[0] == 0:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO admin_agents (id, role, name, description, model_id, skills, tools, prompt_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, role, name, agent_desc, None, "[]", "[]", None, now, now),
            )

    conn.commit()


def init_admin_db():
    conn = _get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS admin_api_keys (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                key_type TEXT NOT NULL,
                cipher_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_llm_models (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                api_key_ref TEXT,
                base_url TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_tools (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_agents (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                model_id TEXT,
                skills TEXT NOT NULL DEFAULT '[]',
                tools TEXT NOT NULL DEFAULT '[]',
                prompt_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_prompts (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                variables TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_prompt_versions (
                id TEXT PRIMARY KEY,
                prompt_id TEXT NOT NULL,
                content TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (prompt_id) REFERENCES admin_prompts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS admin_feishu_config (
                id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL DEFAULT '',
                app_secret_cipher TEXT NOT NULL DEFAULT '',
                ws_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'disabled',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_system_settings (
                id TEXT PRIMARY KEY,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL DEFAULT '',
                description TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_ai_scheduled_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                cron_expr TEXT NOT NULL,
                model_id TEXT,
                prompt_id TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_ai_task_logs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                result TEXT,
                error_message TEXT,
                FOREIGN KEY (task_id) REFERENCES admin_ai_scheduled_tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS admin_ai_logs (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                session_id TEXT,
                model_used TEXT,
                tokens_used INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                prompt_template TEXT,
                source TEXT DEFAULT 'system',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_admin_api_keys_status ON admin_api_keys(status);
            CREATE INDEX IF NOT EXISTS idx_admin_llm_models_status ON admin_llm_models(status);
            CREATE INDEX IF NOT EXISTS idx_admin_agents_role ON admin_agents(role);
            CREATE INDEX IF NOT EXISTS idx_admin_prompts_category ON admin_prompts(category);
            CREATE INDEX IF NOT EXISTS idx_admin_prompt_versions_prompt ON admin_prompt_versions(prompt_id);
            CREATE INDEX IF NOT EXISTS idx_admin_ai_task_logs_task ON admin_ai_task_logs(task_id);
            CREATE INDEX IF NOT EXISTS idx_admin_ai_logs_created ON admin_ai_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_admin_ai_scheduled_tasks_enabled ON admin_ai_scheduled_tasks(enabled);
        """)
        conn.commit()

        _seed_default_data(conn)
    finally:
        conn.close()
