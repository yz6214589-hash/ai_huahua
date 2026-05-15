"""
trader_node -- 交易执行节点

Trader 是团队的交易执行官，负责：
1. 根据批准状态决定是否下单
2. 调用 MiniQMT 接口执行交易
3. 默认 dry-run 模式，不真实下单

输入：state["trade_signal"], state["approved"]
输出：state["trade_result"]
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from workflow.trading_state import TradingState, TradeResult


def trader_node(state: TradingState) -> dict:
    """交易执行节点：根据信号和批准状态执行交易"""
    signal = state.get("trade_signal", {})
    approved = state.get("approved", False)

    print()
    print("=" * 70)
    print("[Trader] 交易执行台")
    print("=" * 70)

    if not approved:
        result = {
            "dry_run": True,
            "order_id": None,
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
            "note": "用户未授权，跳过下单",
        }
        print("[Trader] 用户未授权，跳过下单")
        return {"trade_result": TradeResult(**result), "messages": [{
            "role": "trader",
            "time": datetime.now().strftime("%H:%M:%S"),
            "content": "skipped (not approved)",
        }]}

    if signal.get("direction") == "hold" or signal.get("quantity", 0) <= 0:
        result = {
            "dry_run": True,
            "order_id": None,
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
            "note": "信号为 hold，无需下单",
        }
        print("[Trader] 信号为 hold，无需下单")
        return {"trade_result": TradeResult(**result), "messages": [{
            "role": "trader",
            "time": datetime.now().strftime("%H:%M:%S"),
            "content": "skipped (hold)",
        }]}

    stock = signal.get("stock_code", "")
    qty = int(signal.get("quantity", 0))
    price = float(signal.get("price", 0))
    direction = signal.get("direction", "buy")

    dry_run = os.environ.get("TRADER_DRY_RUN", "1") == "1"

    if dry_run:
        print(f"[Trader] [DRY-RUN] {direction.upper()} {stock} {qty}股 @ {price}")
        result = {
            "dry_run": True,
            "order_id": None,
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
            "note": f"dry-run: {direction} {qty} @ {price}",
        }
        return {"trade_result": TradeResult(**result), "messages": [{
            "role": "trader",
            "time": datetime.now().strftime("%H:%M:%S"),
            "content": result["note"],
        }]}

    try:
        from src.backend.execution import create_execution_task
        task_payload = {
            "symbol": stock,
            "side": direction,
            "total_qty": qty,
            "num_steps": 1,
            "strategy": signal.get("strategy", "macd"),
        }
        task_result = create_execution_task(task_payload)
        result = {
            "dry_run": False,
            "order_id": task_result.get("task_id"),
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
            "note": f"已提交: {direction} {qty} @ {price}",
        }
        print(f"[Trader] 委托编号 {task_result.get('task_id')}")
    except Exception as e:
        result = {
            "dry_run": True,
            "order_id": None,
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
            "note": f"下单失败: {e}",
        }

    return {"trade_result": TradeResult(**result), "messages": [{
        "role": "trader",
        "time": datetime.now().strftime("%H:%M:%S"),
        "content": result.get("note", ""),
    }]}
