"""
执行模块 - 执行任务管理
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.execution.models import ExecutionTask, ExecutionTaskCreate
from core.execution.store import InMemoryStore
from infra.storage.logging_service import get_logger

logger = get_logger("execution")

_STORE = None

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["running", "stopped", "failed"],
    "running": ["finished", "stopped", "failed"],
    "finished": [],
    "stopped": [],
    "failed": ["draft"],
}


def _get_store():
    global _STORE
    if _STORE is not None:
        return _STORE
    _STORE = InMemoryStore()
    logger.info("ExecutionStore 全局实例创建")
    return _STORE


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_status_transition(current: str, target: str) -> str | None:
    allowed = _VALID_TRANSITIONS.get(current, [])
    if target in allowed:
        return None
    return f"状态不能从 {current} 变更为 {target}，允许的目标状态: {', '.join(allowed) if allowed else '无'})"


def get_status() -> dict[str, Any]:
    return {"source": "execution", "status": "ready", "features": ["tasks"], "mode": "embedded"}


def create_execution_task(payload: dict[str, Any]) -> dict[str, Any]:
    req = ExecutionTaskCreate(**payload)
    adv = float(req.adv or 2_000_000)
    task = ExecutionTask(
        id=uuid4().hex,
        symbol=req.symbol,
        side=req.side,
        total_qty=req.total_qty,
        num_steps=req.num_steps,
        strategy=req.strategy,
        rl_model_path=req.rl_model_path,
        impact_eta=req.impact_eta,
        impact_gamma=req.impact_gamma,
        adv=adv,
        constraints=req.constraints,
        status="draft",
        created_at=_now_iso(),
    )
    store = _get_store()
    store.put_task(task)
    logger.info("执行任务创建成功", extra={
        "task_id": task.id,
        "symbol": task.symbol,
        "side": task.side.value,
        "qty": task.total_qty,
        "strategy": task.strategy.value,
    })
    return task.model_dump()


def list_execution_tasks() -> dict[str, Any]:
    store = _get_store()
    items = [x.model_dump() for x in store.list_tasks()]
    logger.info("执行任务列表查询完成", extra={"count": len(items)})
    return {"items": items}


def get_execution_task(task_id: str) -> dict[str, Any] | None:
    store = _get_store()
    task = store.get_task(task_id)
    if not task:
        return None
    return {"task": task.model_dump()}


def update_execution_task(task_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    store = _get_store()
    task = store.get_task(task_id)
    if not task:
        logger.warning("执行任务更新失败，任务不存在", extra={"task_id": task_id})
        return None

    allowed_fields = {"symbol", "side", "total_qty", "num_steps", "strategy",
                       "rl_model_path", "impact_eta", "impact_gamma", "adv",
                       "meta"}
    updates: dict[str, Any] = {}
    for field in allowed_fields:
        if field in payload:
            updates[field] = payload[field]

    if not updates:
        logger.info("执行任务无更新内容", extra={"task_id": task_id})
        return {"task": task.model_dump()}

    updated = store.update_task(task_id, updates)
    if updated is None:
        return None
    logger.info("执行任务更新成功", extra={
        "task_id": task_id,
        "updated_fields": list(updates.keys()),
    })
    return {"task": updated.model_dump()}


def update_execution_task_status(task_id: str, new_status: str, error_msg: str | None = None) -> dict[str, Any] | None:
    store = _get_store()
    task = store.get_task(task_id)
    if not task:
        logger.warning("执行任务状态变更失败，任务不存在", extra={"task_id": task_id})
        return None

    target = str(new_status).lower().strip()
    err = _validate_status_transition(task.status, target)
    if err:
        logger.warning("执行任务状态变更无效", extra={
            "task_id": task_id,
            "current": task.status,
            "target": target,
            "error": err,
        })
        return None

    updates: dict[str, Any] = {"status": target}
    now = _now_iso()
    if target == "running":
        updates["started_at"] = now
    elif target in ("finished", "stopped", "failed"):
        updates["finished_at"] = now
    if target == "failed":
        updates["error"] = str(error_msg or "")

    updated = store.update_task(task_id, updates)
    if updated is None:
        return None
    logger.info("执行任务状态变更成功", extra={
        "task_id": task_id,
        "from": task.status,
        "to": target,
    })
    return {"task": updated.model_dump()}


def delete_execution_task(task_id: str) -> bool:
    store = _get_store()
    result = store.delete_task(task_id)
    if result:
        logger.info("执行任务删除成功", extra={"task_id": task_id})
    else:
        logger.warning("执行任务删除失败，任务不存在", extra={"task_id": task_id})
    return result
