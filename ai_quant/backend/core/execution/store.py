from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.execution.models import ExecutionTask
from infra.storage.logging_service import get_logger

logger = get_logger("execution_store")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


_TASKS_DIR = _project_root() / ".ai_quant" / "execution" / "tasks"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    _TASKS_DIR.mkdir(parents=True, exist_ok=True)


def _task_file_path(task_id: str) -> Path:
    return _TASKS_DIR / f"{task_id}.json"


def _load_tasks_from_disk() -> dict[str, dict[str, Any]]:
    _ensure_dir()
    result: dict[str, dict[str, Any]] = {}
    for p in sorted(_TASKS_DIR.glob("*.json")):
        if p.name.startswith("."):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("id"):
                result[str(data["id"])] = data
        except Exception as e:
            logger.warning("执行任务文件解析失败，已跳过", extra={
                "file": str(p),
                "error": str(e),
            })
    logger.info("执行任务从文件加载完成", extra={"count": len(result)})
    return result


def _write_task_to_disk(task_id: str, data: dict[str, Any]) -> None:
    _ensure_dir()
    tmp = _TASKS_DIR / f".{task_id}.json.tmp"
    out = _task_file_path(task_id)
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(out)
    except Exception as e:
        logger.error("执行任务文件写入失败", extra={
            "task_id": task_id,
            "error": str(e),
            "error_type": type(e).__name__,
        })


def _delete_task_from_disk(task_id: str) -> None:
    p = _task_file_path(task_id)
    if p.exists():
        try:
            p.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("执行任务文件删除失败", extra={
                "task_id": task_id,
                "error": str(e),
            })


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        disk_data = _load_tasks_from_disk()
        self._tasks: dict[str, ExecutionTask] = {}
        for task_id, raw in disk_data.items():
            try:
                self._tasks[task_id] = ExecutionTask(**raw)
            except Exception as e:
                logger.warning("执行任务反序列化失败，已跳过", extra={
                    "task_id": task_id,
                    "error": str(e),
                })
        logger.info("InMemoryStore 初始化完成", extra={
            "from_disk": len(disk_data),
            "loaded": len(self._tasks),
        })

    def put_task(self, task: ExecutionTask) -> None:
        with self._lock:
            self._tasks[str(task.id)] = task
            _write_task_to_disk(task.id, task.model_dump())
            logger.info("执行任务已保存", extra={
                "task_id": task.id,
                "symbol": task.symbol,
                "status": task.status,
            })

    def list_tasks(self) -> list[ExecutionTask]:
        with self._lock:
            return list(self._tasks.values())

    def get_task(self, task_id: str) -> ExecutionTask | None:
        with self._lock:
            return self._tasks.get(str(task_id))

    def update_task(self, task_id: str, updates: dict[str, Any]) -> ExecutionTask | None:
        with self._lock:
            t = self._tasks.get(str(task_id))
            if not t:
                logger.warning("执行任务更新失败，任务不存在", extra={"task_id": task_id})
                return None
            nt = t.model_copy(update=dict(updates))
            self._tasks[str(task_id)] = nt
            _write_task_to_disk(task_id, nt.model_dump())
            logger.info("执行任务已更新", extra={
                "task_id": task_id,
                "new_status": nt.status,
                "updated_fields": list(updates.keys()),
            })
            return nt

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            t = self._tasks.pop(str(task_id), None)
            if t is None:
                return False
            _delete_task_from_disk(task_id)
            logger.info("执行任务已删除", extra={"task_id": task_id})
            return True
