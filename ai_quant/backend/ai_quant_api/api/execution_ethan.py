from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ai_quant_api.services.ethan.integration import (
    create_execution_task,
    get_execution_task,
    get_status,
    list_execution_tasks,
)
from ai_quant_api.runtime.logging_service import get_logger

logger = get_logger("execution")

router = APIRouter(prefix="/api/execution", tags=["execution"])


@router.get("/status")
def execution_status() -> dict[str, object]:
    logger.info("执行状态查询", extra={})
    return get_status()


@router.post("/tasks")
def execution_create_task(body: dict[str, Any]) -> dict[str, Any]:
    logger.info("执行任务创建", extra={
        "symbol": body.get("symbol"),
        "side": body.get("side"),
        "qty": body.get("qty")
    })
    try:
        task = create_execution_task(body)
        logger.info("执行任务创建成功", extra={
            "task_id": task.get("id"),
            "symbol": body.get("symbol"),
            "side": body.get("side")
        })
    except Exception as exc:
        logger.error("执行任务创建失败", extra={
            "symbol": body.get("symbol"),
            "error": str(exc)
        })
        raise HTTPException(status_code=400, detail=str(exc))
    return {"task": task}


@router.get("/tasks")
def execution_list_tasks() -> dict[str, Any]:
    logger.info("执行任务列表查询", extra={})
    return list_execution_tasks()


@router.get("/tasks/{task_id}")
def execution_get_task(task_id: str) -> dict[str, Any]:
    logger.info("执行任务详情查询", extra={
        "task_id": task_id
    })
    item = get_execution_task(task_id)
    if item is None:
        logger.warning("执行任务不存在", extra={
            "task_id": task_id
        })
        raise HTTPException(status_code=404, detail="task not found")
    return item
