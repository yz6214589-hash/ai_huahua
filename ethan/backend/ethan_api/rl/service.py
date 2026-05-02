from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np

from ..models import RLBacktestRequest, RLRun, RLTrainRequest, StrategyType
from ..storage import InMemoryStore
from ..ws.hub import WsHub
from ..execution.order_env import OrderExecutionEnv, TWAPStrategy, VWAPStrategy
from .data_loader import load_stock_data


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    is_vals = [float(r["implementation_shortfall"]) * 10000.0 for r in results]
    slip_vals = [float(r["vwap_slippage"]) * 10000.0 for r in results]
    return {
        "n": len(results),
        "is_mean_bps": float(np.mean(is_vals)) if is_vals else None,
        "is_std_bps": float(np.std(is_vals)) if is_vals else None,
        "vwap_slip_mean_bps": float(np.mean(slip_vals)) if slip_vals else None,
        "vwap_slip_std_bps": float(np.std(slip_vals)) if slip_vals else None,
        "avg_slices": float(np.mean([float(r.get("num_slices") or 0) for r in results])) if results else None,
    }


def _eval_baseline(env: OrderExecutionEnv, strategy_cls, total_qty: int, num_steps: int, n_episodes: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _ in range(int(n_episodes)):
        strategy = strategy_cls(total_qty, num_steps)
        obs, _ = env.reset()
        while True:
            act = strategy.get_action(obs)
            obs, _, term, trunc, _ = env.step(act)
            if term or trunc:
                break
        s = env.get_execution_summary()
        if s:
            out.append(s)
    return out


def _eval_ppo(env: OrderExecutionEnv, model, n_episodes: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _ in range(int(n_episodes)):
        obs, _ = env.reset()
        while True:
            act, _ = model.predict(obs, deterministic=True)
            obs, _, term, trunc, _ = env.step(act)
            if term or trunc:
                break
        s = env.get_execution_summary()
        if s:
            out.append(s)
    return out


def start_train(*, store: InMemoryStore, hub: WsHub, loop: asyncio.AbstractEventLoop, req: RLTrainRequest) -> RLRun:
    run = RLRun(
        id=uuid4().hex,
        symbol=req.symbol,
        start_date=req.start_date,
        end_date=req.end_date,
        timesteps=req.timesteps,
        model_out=req.model_out,
        status="running",
        created_at=_now_iso(),
        started_at=_now_iso(),
    )
    store.put_rl_run(run)

    def _emit(payload: dict[str, Any]) -> None:
        asyncio.run_coroutine_threadsafe(hub.broadcast(f"rl:{run.id}", payload), loop)

    def _worker() -> None:
        try:
            from stable_baselines3 import PPO
            from stable_baselines3.common.vec_env import DummyVecEnv

            df = load_stock_data(req.symbol, req.start_date, req.end_date)
            daily_data_list = [df.iloc[i] for i in range(len(df))]
            adv = float(df["volume"].mean())

            def make_env():
                return OrderExecutionEnv(
                    total_order=req.total_qty,
                    daily_data_list=daily_data_list,
                    adv=adv,
                    num_steps=req.num_steps,
                    impact_eta=req.impact_eta,
                    impact_gamma=req.impact_gamma,
                )

            vec = DummyVecEnv([make_env])
            model = PPO(
                "MlpPolicy",
                vec,
                learning_rate=3e-4,
                n_steps=2048,
                batch_size=64,
                n_epochs=10,
                gamma=0.99,
                gae_lambda=0.95,
                clip_range=0.2,
                ent_coef=0.01,
                verbose=0,
                policy_kwargs={"net_arch": {"pi": [64, 64], "vf": [64, 64]}},
            )

            _emit({"type": "train_started", "run_id": run.id, "timesteps": req.timesteps})
            model.learn(total_timesteps=int(req.timesteps))
            model.save(req.model_out)
            vec.close()

            eval_env = make_env()
            twap = _eval_baseline(eval_env, TWAPStrategy, req.total_qty, req.num_steps, 50)
            vwap = _eval_baseline(eval_env, VWAPStrategy, req.total_qty, req.num_steps, 50)
            ppo = _eval_ppo(eval_env, model, 50)

            metrics = {"twap": _summarize(twap), "vwap": _summarize(vwap), "ppo": _summarize(ppo)}
            store.put_rl_run(store.get_rl_run(run.id).model_copy(update={"status": "finished", "finished_at": _now_iso(), "metrics": metrics}))  # type: ignore
            _emit({"type": "train_finished", "run_id": run.id, "model_out": req.model_out, "metrics": metrics})
        except Exception as e:
            store.put_rl_run(store.get_rl_run(run.id).model_copy(update={"status": "failed", "finished_at": _now_iso(), "error": f"{type(e).__name__}: {e}"}))  # type: ignore
            _emit({"type": "train_failed", "run_id": run.id, "error": f"{type(e).__name__}: {e}"})

    t = threading.Thread(target=_worker, daemon=True)
    store.set_rl_thread(run.id, t)
    t.start()
    return run


def backtest(req: RLBacktestRequest) -> dict[str, Any]:
    from stable_baselines3 import PPO

    df = load_stock_data(req.symbol, req.start_date, req.end_date)
    daily_data_list = [df.iloc[i] for i in range(len(df))]
    adv = float(df["volume"].mean())

    env = OrderExecutionEnv(
        total_order=req.total_qty,
        daily_data_list=daily_data_list,
        adv=adv,
        num_steps=req.num_steps,
        impact_eta=req.impact_eta,
        impact_gamma=req.impact_gamma,
    )

    twap_results = _eval_baseline(env, TWAPStrategy, req.total_qty, req.num_steps, req.n_episodes)
    vwap_results = _eval_baseline(env, VWAPStrategy, req.total_qty, req.num_steps, req.n_episodes)

    rl_summary = None
    if req.rl_model_path:
        model = PPO.load(req.rl_model_path)
        rl_results = _eval_ppo(env, model, req.n_episodes)
        rl_summary = _summarize(rl_results)

    return {"twap": _summarize(twap_results), "vwap": _summarize(vwap_results), "rl": rl_summary}

