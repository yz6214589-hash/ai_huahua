from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ai_quant_api.services.ethan.integration import (
    create_execution_task,
    get_execution_task,
    get_status,
    list_execution_tasks,
)

router = APIRouter(prefix="/api/execution", tags=["execution"])


@router.get("/status")
def execution_status() -> dict[str, object]:
    return get_status()


@router.post("/tasks")
def execution_create_task(body: dict[str, Any]) -> dict[str, Any]:
    try:
        task = create_execution_task(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"task": task}


@router.get("/tasks")
def execution_list_tasks() -> dict[str, Any]:
    return list_execution_tasks()


@router.get("/tasks/{task_id}")
def execution_get_task(task_id: str) -> dict[str, Any]:
    item = get_execution_task(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="task not found")
    return item
