"""
执行模块 - 执行任务管理
负责执行任务的创建、查询、更新、删除和状态管理。
当任务状态变更为 running 时，自动通过 QMT Gateway 执行真实下单。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.execution.models import ExecutionTask, ExecutionTaskCreate
from core.execution.store import InMemoryStore
from infra.qmt_gateway_client import buy as qmt_buy, sell as qmt_sell
from infra.storage.logging_service import get_logger

logger = get_logger("execution")

_STORE = None

# 交易记录持久化文件路径
_TRADE_RECORDS_DIR = Path(__file__).resolve().parents[3] / ".ai_quant" / "execution"
_TRADE_RECORDS_FILE = _TRADE_RECORDS_DIR / "trade_records.json"

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["running", "stopped", "failed"],
    "running": ["finished", "stopped", "failed"],
    "finished": [],
    "stopped": [],
    "failed": ["draft"],
}


def _get_store():
    """获取全局单例的 InMemoryStore 实例（懒加载模式）"""
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


def _persist_trade_record(record: dict[str, Any]) -> None:
    """
    将交易执行记录持久化到 JSON 文件
    每条记录包含：任务ID、股票代码、方向、数量、账户、执行结果、时间等
    """
    _TRADE_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    if _TRADE_RECORDS_FILE.exists():
        try:
            data = json.loads(_TRADE_RECORDS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records = data
        except (json.JSONDecodeError, Exception):
            records = []
    records.append(record)
    tmp = _TRADE_RECORDS_FILE.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(records, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(_TRADE_RECORDS_FILE)
    except Exception as e:
        logger.error("交易记录持久化失败", extra={"error": str(e)})


def _execute_order_via_gateway(task: ExecutionTask) -> dict[str, Any]:
    """
    通过 QMT Gateway 执行真实下单
    从 task.meta 中读取 account_type 确定使用哪个账户
    返回 Gateway 的响应结果
    """
    account_type = task.meta.get("account_type", "")
    if not account_type:
        raise ValueError("任务中缺少 account_type，无法执行下单")

    stock_code = task.symbol
    volume = task.total_qty
    price = float(task.meta.get("price", 0))

    logger.info("通过 QMT Gateway 执行下单", extra={
        "task_id": task.id,
        "symbol": stock_code,
        "side": task.side.value,
        "volume": volume,
        "price": price,
        "account": account_type,
    })

    if task.side.value == "buy":
        result = qmt_buy(
            stock_code=stock_code,
            volume=volume,
            price=price,
            strategy_name="manual",
            remark=f"task:{task.id}",
            account_type=account_type,
        )
    else:
        result = qmt_sell(
            stock_code=stock_code,
            volume=volume,
            price=price,
            strategy_name="manual",
            remark=f"task:{task.id}",
            account_type=account_type,
        )

    return result


def get_status() -> dict[str, Any]:
    return {"source": "execution", "status": "ready", "features": ["tasks"], "mode": "embedded"}


def create_execution_task(payload: dict[str, Any]) -> dict[str, Any]:
    """
    创建新的执行任务
    接收前端传入的参数，构建 ExecutionTask 对象，初始状态为 draft
    支持在 meta 中携带 account_type 等附加信息
    """
    req = ExecutionTaskCreate(**payload)
    task = ExecutionTask(
        id=uuid4().hex,
        symbol=req.symbol,
        side=req.side,
        total_qty=req.total_qty,
        status="draft",
        created_at=_now_iso(),
        meta=payload.get("meta", {}),
    )
    store = _get_store()
    store.put_task(task)
    logger.info("执行任务创建成功", extra={
        "task_id": task.id,
        "symbol": task.symbol,
        "side": task.side.value,
        "qty": task.total_qty,
    })
    return task.model_dump()


def list_execution_tasks() -> dict[str, Any]:
    store = _get_store()
    items = [x.model_dump() for x in store.list_tasks()]
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

    allowed_fields = {"symbol", "side", "total_qty", "meta"}
    updates: dict[str, Any] = {}
    for field in allowed_fields:
        if field in payload:
            updates[field] = payload[field]

    if not updates:
        return {"task": task.model_dump()}

    updated = store.update_task(task_id, updates)
    if updated is None:
        return None
    logger.info("执行任务更新成功", extra={
        "task_id": task_id,
        "updated_fields": list(updates.keys()),
    })
    return {"task": updated.model_dump()}


def update_execution_task_status(
    task_id: str,
    new_status: str,
    error_msg: str | None = None,
    account_type: str | None = None,
) -> dict[str, Any] | None:
    """
    更新执行任务的状态
    执行严格的状态转移校验，非法转移将被拒绝。
    当目标状态为 running 时，自动通过 QMT Gateway 执行真实下单：
      - 下单成功 -> 状态变更为 finished
      - 下单失败 -> 状态变更为 failed 并记录错误信息
    """
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

    now = _now_iso()

    if target == "running":
        # 更新状态为 running 并记录开始时间
        updates: dict[str, Any] = {"status": target, "started_at": now}
        updated = store.update_task(task_id, updates)
        if updated is None:
            return None

        logger.info("执行任务开始执行", extra={
            "task_id": task_id,
            "symbol": task.symbol,
            "side": task.side.value,
            "qty": task.total_qty,
        })

        # 通过 QMT Gateway 执行真实下单
        try:
            order_result = _execute_order_via_gateway(updated)

            # 记录交易执行结果
            trade_record = {
                "task_id": task_id,
                "symbol": task.symbol,
                "side": task.side.value,
                "volume": task.total_qty,
                "price": float(task.meta.get("price", 0)),
                "account_type": task.meta.get("account_type", ""),
                "order_result": order_result,
                "executed_at": now,
                "status": "success",
            }
            _persist_trade_record(trade_record)

            logger.info("执行任务下单成功", extra={
                "task_id": task_id,
                "order_result": str(order_result),
            })

            # 下单成功 -> 标记为 finished
            final_updates: dict[str, Any] = {"status": "finished", "finished_at": _now_iso()}
            final_updates["meta"] = {**updated.meta, "order_result": str(order_result)}
            finished_task = store.update_task(task_id, final_updates)
            if finished_task is None:
                return None
            return {"task": finished_task.model_dump()}

        except Exception as e:
            error_str = str(e)
            logger.error("执行任务下单失败", extra={
                "task_id": task_id,
                "error": error_str,
            })

            # 记录失败交易记录
            _persist_trade_record({
                "task_id": task_id,
                "symbol": task.symbol,
                "side": task.side.value,
                "volume": task.total_qty,
                "price": float(task.meta.get("price", 0)),
                "account_type": task.meta.get("account_type", ""),
                "error": error_str,
                "executed_at": now,
                "status": "failed",
            })

            # 下单失败 -> 标记为 failed 并记录错误
            fail_updates: dict[str, Any] = {"status": "failed", "finished_at": _now_iso(), "error": error_str}
            failed_task = store.update_task(task_id, fail_updates)
            if failed_task is None:
                return None
            return {"task": failed_task.model_dump()}

    elif target in ("stopped", "failed"):
        updates = {"status": target, "finished_at": now}
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

    else:
        # finished 和 draft 状态的普通切换
        updates: dict[str, Any] = {"status": target}
        if target in ("finished",):
            updates["finished_at"] = now
        updated = store.update_task(task_id, updates)
        if updated is None:
            return None
        logger.info("执行任务状态变更成功", extra={
            "task_id": task_id,
            "from": task.status,
            "to": target,
        })
        return {"task": updated.model_dump()}


def delete_execution_task(task_id: str) -> tuple[bool, str]:
    """
    删除指定的执行任务
    仅允许删除 failed（失败）状态的任务
    返回 (是否成功, 错误信息)
    """
    store = _get_store()
    task = store.get_task(task_id)
    if not task:
        return False, "task not found"

    if task.status not in ("failed", "draft", "stopped"):
        logger.warning("执行任务删除被拒绝，仅失败/草稿/已停止任务可删除", extra={
            "task_id": task_id,
            "current_status": task.status,
        })
        return False, f"当前任务状态 ({task.status}) 不允许删除，仅失败/草稿/已停止状态可删除"

    result = store.delete_task(task_id)
    if result:
        logger.info("执行任务删除成功", extra={"task_id": task_id})
    return result, ""


def get_trade_records(limit: int = 100) -> dict[str, Any]:
    """读取持久化的交易执行记录"""
    if _TRADE_RECORDS_FILE.exists():
        try:
            data = json.loads(_TRADE_RECORDS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records = data[-limit:]
                records.reverse()
                return {"records": records, "total": len(data)}
        except (json.JSONDecodeError, Exception):
            pass
    return {"records": [], "total": 0}
