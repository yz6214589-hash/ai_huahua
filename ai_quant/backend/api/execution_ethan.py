from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from core.execution import (
    create_execution_task,
    delete_execution_task,
    get_execution_task,
    get_status,
    list_execution_tasks,
    update_execution_task,
    update_execution_task_status,
)
from infra.storage.logging_service import get_logger

logger = get_logger("execution")

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])


@router.get("/status")
def execution_status() -> dict[str, object]:
    logger.info("执行状态查询", extra={})
    return get_status()


@router.post("/tasks")
def execution_create_task(body: dict[str, Any]) -> dict[str, Any]:
    logger.info("执行任务创建", extra={
        "symbol": body.get("symbol"),
        "side": body.get("side"),
        "qty": body.get("total_qty"),
    })
    try:
        task = create_execution_task(body)
        logger.info("执行任务创建成功", extra={
            "task_id": task.get("id"),
            "symbol": body.get("symbol"),
            "side": body.get("side"),
        })
    except Exception as exc:
        logger.error("执行任务创建失败", extra={
            "symbol": body.get("symbol"),
            "error": str(exc),
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
        "task_id": task_id,
    })
    item = get_execution_task(task_id)
    if item is None:
        logger.warning("执行任务不存在", extra={
            "task_id": task_id,
        })
        raise HTTPException(status_code=404, detail="task not found")
    return item


@router.put("/tasks/{task_id}")
def execution_update_task(task_id: str, body: dict[str, Any]) -> dict[str, Any]:
    logger.info("执行任务更新请求", extra={
        "task_id": task_id,
        "fields": list(body.keys()),
    })
    item = update_execution_task(task_id, body)
    if item is None:
        logger.warning("执行任务更新失败，任务不存在", extra={"task_id": task_id})
        raise HTTPException(status_code=404, detail="task not found")
    logger.info("执行任务更新成功", extra={"task_id": task_id})
    return item


@router.put("/tasks/{task_id}/status")
def execution_update_task_status(task_id: str, body: dict[str, Any]) -> dict[str, Any]:
    new_status = str(body.get("status") or "").strip().lower()
    error_msg = str(body.get("error") or "") if new_status == "failed" else None
    logger.info("执行任务状态变更请求", extra={
        "task_id": task_id,
        "target_status": new_status,
    })
    if new_status not in ("draft", "running", "finished", "stopped", "failed"):
        raise HTTPException(status_code=400, detail=f"无效的状态值: {new_status}")
    item = update_execution_task_status(task_id, new_status, error_msg=error_msg)
    if item is None:
        raise HTTPException(status_code=404, detail="task not found or invalid status transition")
    logger.info("执行任务状态变更成功", extra={
        "task_id": task_id,
        "new_status": new_status,
    })
    return item


@router.delete("/tasks/{task_id}")
def execution_delete_task(task_id: str) -> dict[str, Any]:
    logger.info("执行任务删除请求", extra={"task_id": task_id})
    ok = delete_execution_task(task_id)
    if not ok:
        logger.warning("执行任务删除失败，任务不存在", extra={"task_id": task_id})
        raise HTTPException(status_code=404, detail="task not found")
    return {"ok": True, "task_id": task_id}


@router.get("/positions")
def execution_positions() -> dict[str, Any]:
    logger.info("执行持仓列表查询", extra={})
    try:
        from core.db import connect, load_mysql_config, query_dict
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            positions = query_dict(
                conn,
                "SELECT * FROM trade_sim_position WHERE volume > 0 ORDER BY updated_at DESC",
                ()
            )
            for pos in positions:
                for key in ("created_at", "updated_at", "buy_date"):
                    if pos.get(key):
                        pos[key] = str(pos[key])
            return {"positions": positions, "total": len(positions)}
        finally:
            conn.close()
    except Exception as e:
        logger.error("执行持仓列表查询失败", extra={"error": str(e)})
        return {"positions": [], "total": 0}


@router.get("/records")
def execution_records() -> dict[str, Any]:
    logger.info("执行成交记录查询", extra={})
    try:
        from core.db import connect, load_mysql_config, query_dict
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            records = query_dict(
                conn,
                "SELECT * FROM trade_sim_trade ORDER BY trade_time DESC LIMIT 100",
                ()
            )
            for rec in records:
                for key in ("created_at", "trade_time"):
                    if rec.get(key):
                        rec[key] = str(rec[key])
            return {"records": records, "total": len(records)}
        finally:
            conn.close()
    except Exception as e:
        logger.error("执行成交记录查询失败", extra={"error": str(e)})
        return {"records": [], "total": 0}
