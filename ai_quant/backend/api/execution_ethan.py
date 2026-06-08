from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from core.execution import (
    create_execution_task,
    delete_execution_task,
    get_execution_task,
    get_status,
    get_trade_records,
    list_execution_tasks,
    update_execution_task,
    update_execution_task_status,
)
from infra.qmt_gateway_client import get_positions as qmt_positions, get_orders as qmt_orders, get_trades as qmt_trades
from infra.storage.logging_service import get_logger

logger = get_logger("execution")

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])


@router.get("/status")
def execution_status() -> dict[str, object]:
    """查询执行模块的运行状态"""
    return get_status()


@router.post("/tasks")
def execution_create_task(
    body: dict[str, Any],
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    """创建新的执行任务，account_type 会存入任务的 meta 中供执行时使用"""
    if account_type:
        meta = body.get("meta", {})
        meta["account_type"] = account_type
        body["meta"] = meta
    try:
        task = create_execution_task(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"task": task}


@router.get("/tasks")
def execution_list_tasks() -> dict[str, Any]:
    """获取所有执行任务的列表"""
    return list_execution_tasks()


@router.get("/tasks/{task_id}")
def execution_get_task(task_id: str) -> dict[str, Any]:
    """根据任务ID获取单个执行任务的详细信息"""
    item = get_execution_task(task_id)
    if item is None:
        raise HTTPException(status_code=404, detail="task not found")
    return item


@router.put("/tasks/{task_id}")
def execution_update_task(task_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """更新执行任务的字段"""
    item = update_execution_task(task_id, body)
    if item is None:
        raise HTTPException(status_code=404, detail="task not found")
    return item


@router.put("/tasks/{task_id}/status")
def execution_update_task_status(
    task_id: str,
    body: dict[str, Any],
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    """
    更新执行任务的状态。
    当状态变更为 running 时，自动通过 QMT Gateway 执行真实下单：
      - 下单成功 -> 状态变更为 finished
      - 下单失败 -> 状态变更为 failed
    """
    new_status = str(body.get("status") or "").strip().lower()
    error_msg = str(body.get("error") or "") if new_status == "failed" else None
    if new_status not in ("draft", "running", "finished", "stopped", "failed"):
        raise HTTPException(status_code=400, detail=f"无效的状态值: {new_status}")
    item = update_execution_task_status(task_id, new_status, error_msg=error_msg, account_type=account_type)
    if item is None:
        raise HTTPException(status_code=404, detail="task not found or invalid status transition")
    return item


@router.delete("/tasks/{task_id}")
def execution_delete_task(task_id: str) -> dict[str, Any]:
    """删除指定的执行任务 - 仅允许删除失败状态的任务"""
    ok, err_msg = delete_execution_task(task_id)
    if not ok:
        status_code = 400 if "仅失败任务" in err_msg else 404
        raise HTTPException(status_code=status_code, detail=err_msg)
    return {"ok": True, "task_id": task_id}


@router.get("/positions")
def execution_positions(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    """查询指定账户的实时持仓（通过 QMT Gateway 获取）"""
    try:
        if not account_type:
            return {"positions": [], "total": 0, "error": "缺少 account_type 参数"}
        result = qmt_positions(account_type=account_type)
        positions = result.get("positions") or result.get("result") or []
        if isinstance(positions, list):
            return {"positions": positions, "total": len(positions)}
        return {"positions": [], "total": 0}
    except Exception as e:
        logger.error("执行持仓查询失败", extra={"error": str(e), "account_type": account_type})
        return {"positions": [], "total": 0, "error": str(e)}


@router.get("/orders")
def execution_orders(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    """查询指定账户的当日委托（通过 QMT Gateway 获取）"""
    try:
        if not account_type:
            return {"orders": [], "total": 0, "error": "缺少 account_type 参数"}
        result = qmt_orders(account_type=account_type)
        orders = result.get("orders") or result.get("result") or []
        if isinstance(orders, list):
            return {"orders": orders, "total": len(orders)}
        return {"orders": [], "total": 0}
    except Exception as e:
        logger.error("执行委托查询失败", extra={"error": str(e), "account_type": account_type})
        return {"orders": [], "total": 0, "error": str(e)}


@router.get("/trades")
def execution_trades(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    """查询指定账户的当日成交（通过 QMT Gateway 获取）"""
    try:
        if not account_type:
            return {"trades": [], "total": 0, "error": "缺少 account_type 参数"}
        result = qmt_trades(account_type=account_type)
        trades = result.get("trades") or result.get("result") or []
        if isinstance(trades, list):
            return {"trades": trades, "total": len(trades)}
        return {"trades": [], "total": 0}
    except Exception as e:
        logger.error("执行成交查询失败", extra={"error": str(e), "account_type": account_type})
        return {"trades": [], "total": 0, "error": str(e)}


@router.get("/trade_records")
def execution_trade_records() -> dict[str, Any]:
    """读取持久化的交易执行记录"""
    return get_trade_records()
