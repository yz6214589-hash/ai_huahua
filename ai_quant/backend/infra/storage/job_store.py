"""
Agent运行记录存储模块

本模块负责管理Agent执行运行的历史记录,提供:
- 运行记录的添加和查询（JSON文件持久化）
- 最多保留200条记录
- 线程安全的并发访问控制
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from threading import Lock

from infra.storage.logging_service import get_logger

logger = get_logger("agent_store")


@dataclass
class AgentRunRecord:
    run_id: str
    input: str
    route: str
    created_at: str


_RUNS: list[AgentRunRecord] = []
_LOCK = Lock()
_MAX_RUNS = 200


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


_RUNS_DIR = _project_root() / ".ai_quant" / "agent" / "runs"
_RUNS_INDEX_FILE = _RUNS_DIR / "index.json"


def _ensure_dir() -> None:
    if _RUNS_DIR.exists():
        logger.debug("Agent运行记录目录已存在", extra={"dir_path": str(_RUNS_DIR)})
        return
    try:
        _RUNS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Agent运行记录目录已创建", extra={"dir_path": str(_RUNS_DIR)})
    except Exception as e:
        logger.error("Agent运行记录目录创建失败", extra={
            "dir_path": str(_RUNS_DIR),
            "error": str(e),
            "error_type": type(e).__name__,
        })


def _save_index() -> None:
    _ensure_dir()
    tmp = _RUNS_DIR / ".index.json.tmp"
    try:
        data = [asdict(x) for x in _RUNS]
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        tmp.write_text(json_str, encoding="utf-8")
        tmp.replace(_RUNS_INDEX_FILE)
        logger.info("Agent运行记录索引文件写入成功", extra={
            "file_path": str(_RUNS_INDEX_FILE),
            "record_count": len(data),
            "file_size_bytes": len(json_str.encode("utf-8")),
        })
    except Exception as e:
        logger.error("Agent运行记录索引写入失败", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "file_path": str(_RUNS_INDEX_FILE),
        })


def _load_index() -> list[AgentRunRecord]:
    _ensure_dir()
    if not _RUNS_INDEX_FILE.exists():
        logger.info("Agent运行记录索引文件不存在，返回空列表", extra={
            "file_path": str(_RUNS_INDEX_FILE),
        })
        return []
    try:
        raw = _RUNS_INDEX_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            records = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    records.append(AgentRunRecord(
                        run_id=str(item.get("run_id", "")),
                        input=str(item.get("input", "")),
                        route=str(item.get("route", "")),
                        created_at=str(item.get("created_at", "")),
                    ))
                else:
                    logger.warning("Agent运行记录索引第%d条格式异常，已跳过", extra={
                        "index": i,
                        "actual_type": type(item).__name__,
                    })
            logger.info("Agent运行记录从文件加载完成", extra={"count": len(records)})
            return records
        else:
            logger.warning("Agent运行记录索引文件格式异常，重新开始", extra={
                "expected": "list",
                "actual": type(data).__name__,
            })
    except json.JSONDecodeError as e:
        logger.warning("Agent运行记录索引文件JSON解析失败，重新开始", extra={
            "error": str(e),
            "file_path": str(_RUNS_INDEX_FILE),
        })
    except Exception as e:
        logger.warning("Agent运行记录索引文件读取异常，重新开始", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "file_path": str(_RUNS_INDEX_FILE),
        })
    return []


def _init_runs() -> None:
    global _RUNS
    with _LOCK:
        if not _RUNS:
            logger.info("Agent运行记录开始从磁盘初始化")
            _RUNS = _load_index()
            logger.info("Agent运行记录初始化完成", extra={"loaded_count": len(_RUNS)})
        else:
            logger.debug("Agent运行记录已初始化，跳过重复加载", extra={"current_count": len(_RUNS)})


def append_run(record: AgentRunRecord) -> None:
    _init_runs()
    with _LOCK:
        _RUNS.insert(0, record)
        before_len = len(_RUNS)
        if len(_RUNS) > _MAX_RUNS:
            removed = len(_RUNS) - _MAX_RUNS
            del _RUNS[_MAX_RUNS:]
            logger.debug("Agent运行记录超出上限，已删除旧记录", extra={
                "max": _MAX_RUNS,
                "removed_count": removed,
            })
        _save_index()
        logger.info("Agent运行记录已保存", extra={
            "run_id": record.run_id,
            "route": record.route,
            "total": len(_RUNS),
            "input_preview": record.input[:80],
        })


def list_runs() -> list[dict[str, str]]:
    _init_runs()
    with _LOCK:
        result = [asdict(x) for x in _RUNS]
        logger.debug("Agent运行记录列表查询", extra={"count": len(result)})
        return result


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
