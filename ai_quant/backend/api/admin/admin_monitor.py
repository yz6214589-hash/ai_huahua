"""
日志与监控API路由模块

提供系统状态监控、实时日志查询和日志统计功能。
日志数据读取自文件系统，系统状态综合多个数据源。
响应格式统一为 {"ok": true, "data": ...} 或 {"ok": false, "error": "..."}
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query

from ..admin_db import get_admin_db

router = APIRouter(prefix="/api/v1/admin/monitor", tags=["admin-monitor"])


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _get_log_dir() -> Path:
    import os
    log_dir_env = os.getenv("AI_QUANT_LOG_DIR", "").strip()
    if log_dir_env:
        return Path(log_dir_env)
    return _project_root() / ".ai_quant" / "logs"


def _parse_log_line(line: str) -> dict | None:
    pattern = r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[([\w.]+)\] \[(\w+)\] (.+)$"
    match = re.match(pattern, line.strip())
    if not match:
        return None
    timestamp_str, module, level, message = match.groups()
    try:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return {
        "timestamp": timestamp.isoformat(),
        "module": module,
        "level": level,
        "message": message,
    }


def _is_feishu_bot_running() -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", "feishu/bot.py"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _get_feishu_config() -> dict | None:
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT app_id, status FROM admin_feishu_config LIMIT 1"
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def _count_ai_logs_today() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) as total, "
                "COALESCE(SUM(CASE WHEN source = 'api' THEN 1 ELSE 0 END), 0) as api_calls, "
                "COALESCE(SUM(CASE WHEN source != 'api' THEN 1 ELSE 0 END), 0) as messages "
                "FROM admin_ai_logs WHERE created_at >= ?",
                (today,),
            )
            row = cur.fetchone()
            return dict(row) if row else {"total": 0, "api_calls": 0, "messages": 0}
        finally:
            conn.close()


@router.get("/status")
def get_system_status():
    feishu_config = _get_feishu_config()
    feishu_connected = False
    if feishu_config and feishu_config.get("status") == "enabled":
        feishu_connected = _is_feishu_bot_running()

    log_stats = _count_ai_logs_today()

    # 检查各个API进程状态
    services = {
        "api_server": True,
        "feishu_bot": feishu_connected if feishu_config else False,
    }

    return {
        "ok": True,
        "data": {
            "services": services,
            "feishu": {
                "configured": feishu_config is not None,
                "connected": feishu_connected,
                "app_id": feishu_config.get("app_id", "") if feishu_config else "",
                "status": feishu_config.get("status", "disabled") if feishu_config else "disabled",
            },
            "stats": {
                "api_calls_today": log_stats.get("api_calls", 0),
                "messages_today": log_stats.get("messages", 0),
                "total_logs_today": log_stats.get("total", 0),
            },
            "server_time": datetime.now().isoformat(),
        },
    }


@router.get("/logs")
def get_monitor_logs(
    level: str = Query(default=None, description="日志级别筛选（DEBUG、INFO、WARNING、ERROR、CRITICAL）"),
    module: str = Query(default=None, description="模块筛选"),
    limit: int = Query(default=100, ge=1, le=1000, description="返回记录数量"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    q: str = Query(default=None, description="关键词搜索"),
):
    log_dir = _get_log_dir()
    if not log_dir.exists():
        return {"ok": True, "data": {"logs": [], "total": 0, "limit": limit, "offset": offset}}

    all_logs = []
    if module:
        log_file = log_dir / f"{module}.log"
        if log_file.exists():
            all_log_files = [log_file]
        else:
            all_log_files = []
    else:
        all_log_files = list(log_dir.glob("*.log"))

    for log_file in all_log_files:
        try:
            content = log_file.read_text(encoding="utf-8")
            lines = content.strip().split("\n") if content.strip() else []
            for line in lines:
                parsed = _parse_log_line(line)
                if parsed:
                    parsed["file"] = log_file.name
                    all_logs.append(parsed)
        except Exception:
            continue

    if level:
        level_upper = level.upper()
        all_logs = [log for log in all_logs if log["level"] == level_upper]

    if q:
        q_lower = q.lower()
        all_logs = [log for log in all_logs if q_lower in log["message"].lower()]

    all_logs.sort(key=lambda x: x["timestamp"], reverse=True)
    total = len(all_logs)
    paginated = all_logs[offset:offset + limit]

    return {
        "ok": True,
        "data": {
            "logs": paginated,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/logs/stats")
def get_monitor_logs_stats():
    log_dir = _get_log_dir()
    if not log_dir.exists():
        return {
            "ok": True,
            "data": {
                "summary": {"total": 0, "by_level": {}, "by_module": {}},
                "disk_usage": {"total_bytes": 0, "total_mb": 0.0},
            },
        }

    level_counts: dict[str, int] = {}
    module_counts: dict[str, int] = {}
    total_lines = 0
    total_bytes = 0

    log_files = list(log_dir.glob("*.log"))
    for log_file in log_files:
        try:
            content = log_file.read_text(encoding="utf-8")
            lines = content.strip().split("\n") if content.strip() else []
            file_lines = len(lines)
            total_lines += file_lines
            total_bytes += log_file.stat().st_size
            module_name = log_file.stem
            module_lines = 0
            for line in lines:
                parsed = _parse_log_line(line)
                if parsed:
                    level = parsed["level"]
                    level_counts[level] = level_counts.get(level, 0) + 1
                    module_lines += 1
            module_counts[module_name] = module_counts.get(module_name, 0) + module_lines
        except Exception:
            continue

    return {
        "ok": True,
        "data": {
            "summary": {
                "total": total_lines,
                "by_level": dict(sorted(level_counts.items())),
                "by_module": dict(sorted(module_counts.items())),
            },
            "disk_usage": {
                "total_bytes": total_bytes,
                "total_mb": round(total_bytes / (1024 * 1024), 2),
            },
            "files_count": len(log_files),
        },
    }
