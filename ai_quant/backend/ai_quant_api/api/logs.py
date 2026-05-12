"""
日志查询 API 模块

提供日志查询和统计接口，便于运维和问题排查
支持按模块、级别、时间范围过滤和关键词搜索
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _project_root() -> Path:
    """获取项目根目录路径"""
    return Path(__file__).resolve().parents[2]


def _get_log_dir() -> Path:
    """获取日志目录路径"""
    import os

    log_dir_env = os.getenv("AI_QUANT_LOG_DIR", "").strip()
    if log_dir_env:
        return Path(log_dir_env)
    return _project_root() / ".ai_quant" / "logs"


def _parse_log_line(line: str) -> dict[str, Any] | None:
    """
    解析单行日志

    日志格式：[时间戳] [模块] [级别] 消息
    例如：[2026-05-11 14:30:45] [reports] [INFO] 任务开始

    Args:
        line: 日志行

    Returns:
        解析后的字典，解析失败返回 None
    """
    pattern = r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[([\w.]+)\] \[(\w+)\] (.+)$"
    match = re.match(pattern, line.strip())
    if not match:
        return None

    timestamp_str, module, level, message = match.groups()

    try:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    extra = {}
    extra_pattern = r'(\w+)=("[^"]*"|\S+)'
    extra_matches = re.findall(extra_pattern, message)
    for key, value in extra_matches:
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        extra[key] = value

    clean_message = message
    for key in extra:
        pattern = rf'\s*{key}="?{re.escape(str(extra[key]))}"?\s*'
        clean_message = re.sub(pattern, '', clean_message)
    clean_message = clean_message.strip()

    return {
        "timestamp": timestamp.isoformat(),
        "module": module,
        "level": level,
        "message": clean_message,
        "extra": extra
    }


@router.get("")
def logs_query(
    module: str = Query(default=None, description="模块名称过滤"),
    level: str = Query(default=None, description="日志级别过滤（DEBUG、INFO、WARNING、ERROR、CRITICAL）"),
    start_time: str = Query(default=None, description="开始时间（ISO 格式）"),
    end_time: str = Query(default=None, description="结束时间（ISO 格式）"),
    limit: int = Query(default=100, ge=1, le=1000, description="返回记录数量"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    q: str = Query(default=None, description="关键词搜索"),
) -> dict[str, Any]:
    """
    查询日志记录

    支持多维度过滤和分页查询

    Args:
        module: 模块名称过滤
        level: 日志级别过滤
        start_time: 开始时间（ISO 格式）
        end_time: 结束时间（ISO 格式）
        limit: 返回记录数量（默认 100，最大 1000）
        offset: 偏移量
        q: 关键词搜索

    Returns:
        包含日志记录列表和统计信息的字典
    """
    log_dir = _get_log_dir()
    if not log_dir.exists():
        return {
            "logs": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "message": "日志目录不存在"
        }

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

    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            all_logs = [log for log in all_logs
                       if datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00")) >= start_dt]
        except ValueError:
            pass

    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            all_logs = [log for log in all_logs
                       if datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00")) <= end_dt]
        except ValueError:
            pass

    if q:
        q_lower = q.lower()
        all_logs = [log for log in all_logs
                   if q_lower in log["message"].lower() or
                      q_lower in log.get("extra", {}).values()]

    all_logs.sort(key=lambda x: x["timestamp"], reverse=True)

    total = len(all_logs)
    paginated_logs = all_logs[offset:offset + limit]

    return {
        "logs": paginated_logs,
        "total": total,
        "limit": limit,
        "offset": offset,
        "files_count": len(all_log_files)
    }


@router.get("/stats")
def logs_stats() -> dict[str, Any]:
    """
    获取日志统计信息

    统计各模块和各级别的日志数量，以及磁盘使用情况

    Returns:
        包含统计信息的字典
    """
    log_dir = _get_log_dir()
    if not log_dir.exists():
        return {
            "summary": {
                "total": 0,
                "by_level": {},
                "by_module": {}
            },
            "disk_usage": {
                "total_bytes": 0,
                "total_mb": 0.0
            },
            "message": "日志目录不存在"
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
        "summary": {
            "total": total_lines,
            "by_level": dict(sorted(level_counts.items())),
            "by_module": dict(sorted(module_counts.items()))
        },
        "disk_usage": {
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2)
        },
        "files_count": len(log_files)
    }


@router.get("/files")
def logs_files() -> dict[str, Any]:
    """
    获取日志文件列表

    Returns:
        包含日志文件列表的字典
    """
    log_dir = _get_log_dir()
    if not log_dir.exists():
        return {
            "files": [],
            "message": "日志目录不存在"
        }

    log_files = []
    for log_file in sorted(log_dir.glob("*.log")):
        try:
            stat = log_file.stat()
            log_files.append({
                "name": log_file.name,
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        except Exception:
            continue

    return {
        "files": log_files,
        "total_files": len(log_files)
    }
