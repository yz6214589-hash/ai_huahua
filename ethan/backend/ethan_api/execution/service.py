from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np

from ..models import ExecutionTask, ExecutionTaskCreate, SimulationRequest, StrategyType
from ..storage import ExecutionRuntime, InMemoryStore
from ..trading.miniqmt_trader import MiniQMTTrader
from ..ws.hub import WsHub
from .order_env import OrderExecutionEnv, TWAPStrategy, VWAPStrategy


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_task(req: ExecutionTaskCreate, adv: float) -> ExecutionTask:
    return ExecutionTask(
        id=uuid4().hex,
        symbol=req.symbol,
        side=req.side,
        total_qty=req.total_qty,
        num_steps=req.num_steps,
        strategy=req.strategy,
        rl_model_path=req.rl_model_path,
        impact_eta=req.impact_eta,
        impact_gamma=req.impact_gamma,
        adv=float(adv),
        constraints=req.constraints,
        status="draft",
        created_at=_now_iso(),
    )


def _build_strategy(task: ExecutionTask):
    if task.strategy == StrategyType.twap:
        return TWAPStrategy(task.total_qty, task.num_steps), None
    if task.strategy == StrategyType.vwap:
        return VWAPStrategy(task.total_qty, task.num_steps), None
    if task.strategy == StrategyType.rl:
        from stable_baselines3 import PPO

        if not task.rl_model_path:
            raise ValueError("rl_model_path required")
        model = PPO.load(task.rl_model_path)

        class _RL:
            def get_action(self, obs: np.ndarray) -> np.ndarray:
                act, _ = model.predict(obs, deterministic=True)
                return act

        return _RL(), model
    raise ValueError("unknown strategy")


def simulate(task: ExecutionTask, daily_data_list: list, req: SimulationRequest) -> list[dict[str, Any]]:
    env = OrderExecutionEnv(
        total_order=task.total_qty,
        daily_data_list=daily_data_list,
        adv=task.adv,
        num_steps=task.num_steps,
        impact_eta=task.impact_eta,
        impact_gamma=task.impact_gamma,
    )
    strategy, _ = _build_strategy(task)

    out: list[dict[str, Any]] = []
    for ep in range(int(req.n_episodes)):
        obs, _ = env.reset(seed=req.seed)
        while True:
            action = strategy.get_action(obs)
            obs, _, terminated, truncated, _ = env.step(action)
            if terminated or truncated:
                break
        summary = env.get_execution_summary()
        if summary:
            out.append({"summary": summary, "history": dict(env.history)})
    return out


def _calc_max_participation_qty(task: ExecutionTask) -> int:
    per_step_vol = float(task.adv) / float(task.num_steps)
    return int(max(0.0, float(task.constraints.max_participation_rate) * per_step_vol))


def start_execution(
    *,
    store: InMemoryStore,
    hub: WsHub,
    loop: asyncio.AbstractEventLoop,
    task_id: str,
    trader: MiniQMTTrader,
) -> None:
    task = store.get_task(task_id)
    if not task:
        raise ValueError("task not found")
    if task.status == "running":
        return

    stop_flag = threading.Event()
    rt = ExecutionRuntime(stop_flag=stop_flag)

    def _emit(payload: dict[str, Any]) -> None:
        asyncio.run_coroutine_threadsafe(hub.broadcast(f"exec:{task_id}", payload), loop)

    def _worker() -> None:
        t0 = task
        store.put_task(t0.model_copy(update={"status": "running", "started_at": _now_iso(), "error": None}))
        _emit({"type": "task_status", "status": "running", "task_id": task_id})

        try:
            strategy, _ = _build_strategy(t0)

            total = int(t0.total_qty)
            executed_qty = 0
            executed_cost = 0.0
            arrival_price: float | None = None

            max_participation_qty = _calc_max_participation_qty(t0)
            max_single = int(t0.constraints.max_single_order_qty)
            retry = t0.constraints.cancel_retry

            for step in range(int(t0.num_steps)):
                if stop_flag.is_set():
                    break

                remaining = total - executed_qty
                if remaining <= 0:
                    break

                if step == int(t0.num_steps) - 1:
                    slice_qty = remaining
                else:
                    remaining_ratio = float(remaining) / float(total)
                    time_ratio = float(t0.num_steps - step) / float(t0.num_steps)
                    obs = np.array([remaining_ratio, time_ratio, 0.0, 0.02, 0.0], dtype=np.float32)
                    action = strategy.get_action(obs)
                    exec_ratio = float(np.clip(float(action[0]), 0.0, 1.0))
                    slice_qty = int(float(remaining) * exec_ratio)

                slice_qty = min(slice_qty, remaining)
                if max_participation_qty > 0:
                    slice_qty = min(slice_qty, max_participation_qty)
                slice_qty = min(slice_qty, max_single)
                if slice_qty <= 0:
                    _emit({"type": "step_skip", "step": step, "reason": "slice_qty<=0"})
                    continue

                _emit({"type": "step_start", "step": step, "slice_qty": slice_qty, "remaining": remaining})

                target_left = int(slice_qty)
                last_order_id: int | None = None
                filled_total = 0
                filled_amount_total = 0.0

                for attempt in range(int(retry.max_retries) + 1):
                    if stop_flag.is_set():
                        break
                    if target_left <= 0:
                        break

                    if t0.side.value == "buy":
                        order_id = trader.buy(t0.symbol, target_left, price=0.0, strategy_name="ethan_exec", remark=f"{task_id}:{step}:{attempt}")
                    else:
                        order_id = trader.sell(t0.symbol, target_left, price=0.0, strategy_name="ethan_exec", remark=f"{task_id}:{step}:{attempt}")

                    if order_id is None:
                        raise RuntimeError("place_order_failed")

                    last_order_id = int(order_id)
                    _emit({"type": "order_placed", "step": step, "attempt": attempt, "order_id": last_order_id, "qty": target_left})

                    if float(retry.wait_seconds) > 0:
                        time.sleep(float(retry.wait_seconds))

                    trades = trader.query_trades()
                    order_trades = [x for x in trades if int(x.get("order_id") or 0) == last_order_id]
                    vol_filled = int(sum(int(x.get("traded_volume") or 0) for x in order_trades))
                    amt_filled = float(sum(float(x.get("traded_amount") or 0.0) for x in order_trades))

                    if vol_filled > 0:
                        filled_total += vol_filled
                        filled_amount_total += amt_filled
                        target_left = max(0, int(target_left) - int(vol_filled))

                    if target_left <= 0:
                        _emit({"type": "order_filled", "step": step, "order_id": last_order_id, "filled_qty": vol_filled})
                        break

                    if attempt < int(retry.max_retries):
                        trader.cancel(last_order_id)
                        _emit({"type": "order_canceled", "step": step, "order_id": last_order_id, "left_qty": target_left})

                if filled_total > 0:
                    avg_price = (filled_amount_total / float(filled_total)) if filled_amount_total > 0 else None
                    executed_qty += int(filled_total)
                    if avg_price is not None:
                        executed_cost += float(avg_price) * float(filled_total)
                        if arrival_price is None:
                            arrival_price = float(avg_price)
                else:
                    _emit({"type": "step_no_fill", "step": step, "order_id": last_order_id})

                vwap = (executed_cost / float(executed_qty)) if executed_qty > 0 else None
                slippage_bps = None
                if arrival_price is not None and vwap is not None and arrival_price > 0:
                    slippage_bps = (float(vwap) - float(arrival_price)) / float(arrival_price) * 10000.0
                    if abs(float(slippage_bps)) >= float(t0.constraints.slippage_alert_bps):
                        _emit({"type": "alert", "step": step, "name": "slippage", "slippage_bps": float(slippage_bps)})

                _emit(
                    {
                        "type": "step_done",
                        "step": step,
                        "executed_qty": executed_qty,
                        "remaining_qty": total - executed_qty,
                        "vwap": vwap,
                        "arrival_price": arrival_price,
                        "slippage_bps": slippage_bps,
                    }
                )

            status = "finished" if executed_qty >= total else ("stopped" if stop_flag.is_set() else "stopped")
            store.put_task(store.get_task(task_id).model_copy(update={"status": status, "finished_at": _now_iso()}))  # type: ignore
            _emit({"type": "task_status", "status": status, "task_id": task_id})
        except Exception as e:
            store.put_task(store.get_task(task_id).model_copy(update={"status": "failed", "finished_at": _now_iso(), "error": f"{type(e).__name__}: {e}"}))  # type: ignore
            _emit({"type": "task_status", "status": "failed", "task_id": task_id, "error": f"{type(e).__name__}: {e}"})
        finally:
            store.delete_task_runtime(task_id)

    th = threading.Thread(target=_worker, daemon=True)
    rt.thread = th
    store.set_task_runtime(task_id, rt)
    th.start()


def stop_execution(store: InMemoryStore, task_id: str) -> bool:
    rt = store.get_task_runtime(task_id)
    if not rt:
        return False
    rt.stop_flag.set()
    return True
