from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class MainForceTask:
    task_id: str
    stock_code: str
    company_name: str | None
    mode: str
    params: dict[str, Any]
    status: str
    created_at: str
    updated_at: str
    result: dict[str, Any]
    artifacts: dict[str, Any]


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


def load_tasks(path: str) -> list[MainForceTask]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f) or []
    out: list[MainForceTask] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("task_id", "")).strip()
        stock_code = str(item.get("stock_code", "")).strip()
        company_name = item.get("company_name")
        company_name = str(company_name).strip() if isinstance(company_name, str) and company_name.strip() else None
        mode = str(item.get("mode", "simulated")).strip() or "simulated"
        params = item.get("params") if isinstance(item.get("params"), dict) else {}
        status = str(item.get("status", "pending")).strip() or "pending"
        created_at = str(item.get("created_at", "")).strip()
        updated_at = str(item.get("updated_at", "")).strip()
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        artifacts = item.get("artifacts") if isinstance(item.get("artifacts"), dict) else {}
        if task_id and stock_code:
            out.append(
                MainForceTask(
                    task_id=task_id,
                    stock_code=stock_code,
                    company_name=company_name,
                    mode=mode,
                    params=params,
                    status=status,
                    created_at=created_at,
                    updated_at=updated_at,
                    result=result,
                    artifacts=artifacts,
                )
            )
    out.sort(key=lambda x: x.updated_at or x.created_at or "", reverse=True)
    return out


def save_tasks(path: str, tasks: list[MainForceTask]) -> None:
    _ensure_parent(path)
    data = []
    for t in tasks:
        data.append(
            {
                "task_id": t.task_id,
                "stock_code": t.stock_code,
                "company_name": t.company_name,
                "mode": t.mode,
                "params": t.params,
                "status": t.status,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                "result": t.result,
                "artifacts": t.artifacts,
            }
        )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_tasks(path: str) -> list[MainForceTask]:
    return load_tasks(path)


def get_task(path: str, task_id: str) -> MainForceTask | None:
    tid = str(task_id or "").strip()
    if not tid:
        return None
    for t in load_tasks(path):
        if t.task_id == tid:
            return t
    return None


def create_task(stock_code: str, company_name: str | None, params: dict[str, Any], tasks_path: str) -> MainForceTask:
    now = datetime.now().isoformat(timespec="seconds")
    return MainForceTask(
        task_id=str(uuid4()),
        stock_code=str(stock_code or "").strip(),
        company_name=str(company_name).strip() if isinstance(company_name, str) and company_name.strip() else None,
        mode="simulated",
        params=params or {},
        status="pending",
        created_at=now,
        updated_at=now,
        result={},
        artifacts={},
    )


def upsert_task(path: str, task: MainForceTask) -> None:
    tasks = load_tasks(path)
    tasks = [t for t in tasks if t.task_id != task.task_id]
    tasks.append(task)
    save_tasks(path, tasks)


def delete_task(path: str, task_id: str) -> bool:
    tasks = load_tasks(path)
    new_tasks = [t for t in tasks if t.task_id != task_id]
    if len(new_tasks) == len(tasks):
        return False
    save_tasks(path, new_tasks)
    return True

