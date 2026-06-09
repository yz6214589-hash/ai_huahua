"""
AI分析日志记录器模块

负责记录AI分析日志到 admin_ai_logs 表，以及提供日志查询和统计功能。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ...api.admin_db import get_admin_db


class AILogger:
    """AI分析日志记录器"""

    @staticmethod
    def log(
        conversation_id: str,
        session_id: str,
        model_used: str,
        tokens_used: int,
        duration_ms: int,
        prompt_template: str,
        source: str = "system",
    ):
        """记录AI分析日志到 admin_ai_logs 表"""
        try:
            log_id = uuid.uuid4().hex
            now = datetime.now().isoformat()
            conn, lock = get_admin_db()
            with lock:
                conn.execute(
                    "INSERT INTO admin_ai_logs (id, conversation_id, session_id, model_used, "
                    "tokens_used, duration_ms, prompt_template, source, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        log_id,
                        conversation_id,
                        session_id,
                        model_used,
                        int(tokens_used),
                        int(duration_ms),
                        prompt_template,
                        source,
                        now,
                    ),
                )
                conn.commit()
                conn.close()
        except Exception:
            pass

    @staticmethod
    def get_logs(page: int = 1, page_size: int = 20, **filters) -> dict:
        """查询AI日志（分页）"""
        try:
            conn, lock = get_admin_db()
            with lock:
                cur = conn.cursor()

                where_clauses: list[str] = []
                params: list[Any] = []

                if filters.get("conversation_id"):
                    where_clauses.append("conversation_id = ?")
                    params.append(filters["conversation_id"])
                if filters.get("session_id"):
                    where_clauses.append("session_id = ?")
                    params.append(filters["session_id"])
                if filters.get("source"):
                    where_clauses.append("source = ?")
                    params.append(filters["source"])
                if filters.get("model_used"):
                    where_clauses.append("model_used = ?")
                    params.append(filters["model_used"])
                if filters.get("start_time"):
                    where_clauses.append("created_at >= ?")
                    params.append(filters["start_time"])
                if filters.get("end_time"):
                    where_clauses.append("created_at <= ?")
                    params.append(filters["end_time"])

                where_sql = ""
                if where_clauses:
                    where_sql = "WHERE " + " AND ".join(where_clauses)

                # 查询总数
                cur.execute(
                    f"SELECT COUNT(*) FROM admin_ai_logs {where_sql}", params
                )
                total = cur.fetchone()[0]

                # 分页查询
                offset = (max(1, page) - 1) * max(1, page_size)
                limit = max(1, page_size)
                cur.execute(
                    f"SELECT id, conversation_id, session_id, model_used, tokens_used, "
                    f"duration_ms, prompt_template, source, created_at "
                    f"FROM admin_ai_logs {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    params + [limit, offset],
                )
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()

                return {
                    "ok": True,
                    "data": rows,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                }
        except Exception as e:
            return {"ok": False, "error": str(e), "data": [], "total": 0, "page": page, "page_size": page_size}

    @staticmethod
    def get_stats() -> dict:
        """获取AI日志统计（总调用次数、平均耗时、模型分布等）"""
        try:
            conn, lock = get_admin_db()
            with lock:
                cur = conn.cursor()

                # 总调用次数
                cur.execute("SELECT COUNT(*) FROM admin_ai_logs")
                total_calls = cur.fetchone()[0]

                # 平均耗时
                cur.execute(
                    "SELECT AVG(duration_ms) FROM admin_ai_logs WHERE duration_ms > 0"
                )
                avg_duration_ms = cur.fetchone()[0] or 0

                # 总token数
                cur.execute("SELECT SUM(tokens_used) FROM admin_ai_logs")
                total_tokens = cur.fetchone()[0] or 0

                # 模型分布
                cur.execute(
                    "SELECT model_used, COUNT(*) as count FROM admin_ai_logs "
                    "WHERE model_used IS NOT NULL AND model_used != '' "
                    "GROUP BY model_used ORDER BY count DESC"
                )
                model_distribution = [dict(r) for r in cur.fetchall()]

                # 来源分布
                cur.execute(
                    "SELECT source, COUNT(*) as count FROM admin_ai_logs "
                    "WHERE source IS NOT NULL AND source != '' "
                    "GROUP BY source ORDER BY count DESC"
                )
                source_distribution = [dict(r) for r in cur.fetchall()]

                # 今日调用次数
                today = datetime.now().strftime("%Y-%m-%d")
                cur.execute(
                    "SELECT COUNT(*) FROM admin_ai_logs WHERE created_at >= ?",
                    (today,),
                )
                today_calls = cur.fetchone()[0]

                conn.close()

                return {
                    "ok": True,
                    "data": {
                        "total_calls": total_calls,
                        "today_calls": today_calls,
                        "avg_duration_ms": round(float(avg_duration_ms), 2),
                        "total_tokens": total_tokens,
                        "model_distribution": model_distribution,
                        "source_distribution": source_distribution,
                    },
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}
