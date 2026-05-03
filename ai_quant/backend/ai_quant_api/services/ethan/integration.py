from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


_STORE = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _ensure_ethan_import_path() -> None:
    p = str(_project_root() / "ethan" / "backend")
    if p not in sys.path:
        sys.path.insert(0, p)


def _get_store():
    global _STORE
    if _STORE is not None:
        return _STORE
    _ensure_ethan_import_path()
    from ethan_api.storage import InMemoryStore  # type: ignore

    _STORE = InMemoryStore()
    return _STORE


def get_status() -> dict[str, Any]:
    return {"source": "ethan", "status": "ready", "features": ["tasks", "sim", "trading"]}


def create_execution_task(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_ethan_import_path()
    from ethan_api.execution.service import create_task  # type: ignore
    from ethan_api.models import ExecutionTaskCreate  # type: ignore

    req = ExecutionTaskCreate(**payload)
    adv = float(req.adv or 2_000_000)
    task = create_task(req, adv=adv)
    store = _get_store()
    store.put_task(task)
    return task.model_dump()


def list_execution_tasks() -> dict[str, Any]:
    store = _get_store()
    return {"items": [x.model_dump() for x in store.list_tasks()]}


def get_execution_task(task_id: str) -> dict[str, Any] | None:
    store = _get_store()
    task = store.get_task(task_id)
    if not task:
        return None
    return {"task": task.model_dump()}
