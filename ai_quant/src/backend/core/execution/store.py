from __future__ import annotations

import threading
from typing import Any

from src.backend.execution.models import ExecutionTask


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, ExecutionTask] = {}

    def put_task(self, task: ExecutionTask) -> None:
        with self._lock:
            self._tasks[str(task.id)] = task

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
                return None
            nt = t.model_copy(update=dict(updates))
            self._tasks[str(task_id)] = nt
            return nt

