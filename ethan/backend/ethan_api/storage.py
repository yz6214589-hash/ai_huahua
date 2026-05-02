from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from .models import ExecutionTask, RLRun


@dataclass
class ExecutionRuntime:
    stop_flag: threading.Event
    thread: threading.Thread | None = None
    state: dict[str, Any] | None = None


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, ExecutionTask] = {}
        self._task_runtime: dict[str, ExecutionRuntime] = {}
        self._rl_runs: dict[str, RLRun] = {}
        self._rl_threads: dict[str, threading.Thread] = {}

    def put_task(self, task: ExecutionTask) -> None:
        with self._lock:
            self._tasks[task.id] = task

    def get_task(self, task_id: str) -> ExecutionTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> list[ExecutionTask]:
        with self._lock:
            return list(self._tasks.values())

    def set_task_runtime(self, task_id: str, runtime: ExecutionRuntime) -> None:
        with self._lock:
            self._task_runtime[task_id] = runtime

    def get_task_runtime(self, task_id: str) -> ExecutionRuntime | None:
        with self._lock:
            return self._task_runtime.get(task_id)

    def delete_task_runtime(self, task_id: str) -> None:
        with self._lock:
            self._task_runtime.pop(task_id, None)

    def put_rl_run(self, run: RLRun) -> None:
        with self._lock:
            self._rl_runs[run.id] = run

    def get_rl_run(self, run_id: str) -> RLRun | None:
        with self._lock:
            return self._rl_runs.get(run_id)

    def list_rl_runs(self) -> list[RLRun]:
        with self._lock:
            return list(self._rl_runs.values())

    def set_rl_thread(self, run_id: str, t: threading.Thread) -> None:
        with self._lock:
            self._rl_threads[run_id] = t

    def get_rl_thread(self, run_id: str) -> threading.Thread | None:
        with self._lock:
            return self._rl_threads.get(run_id)

