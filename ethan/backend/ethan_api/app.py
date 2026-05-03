from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from .agent.graph import build_graph
from .execution.service import create_task, simulate, start_execution, stop_execution
from .models import ExecutionTaskCreate, RLBacktestRequest, RLTrainRequest, SimulationRequest
from .rl.data_loader import load_stock_data
from .rl.service import backtest, start_train
from .storage import InMemoryStore
from .trading.miniqmt_trader import MiniQMTTrader
from .ws.hub import WsHub


def create_app() -> FastAPI:
    app = FastAPI(title="Ethan API", version="0.1.0")

    def err_detail(code: str, message: str, hint: str | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {"code": code, "message": message}
        if hint:
            d["hint"] = hint
        return d

    cors_env = str(os.getenv("ETHAN_CORS_ORIGINS") or "").strip()
    cors_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    cors_kwargs: dict[str, Any]
    if cors_origins:
        cors_kwargs = {"allow_origins": cors_origins}
    else:
        cors_kwargs = {
            "allow_origins": [],
            "allow_origin_regex": r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        }
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        **cors_kwargs,
    )

    app.state.store = InMemoryStore()
    app.state.hub = WsHub()
    app.state.loop = None
    app.state.trader = None
    app.state.graph = build_graph()

    @app.on_event("startup")
    async def _startup() -> None:
        app.state.loop = asyncio.get_running_loop()

    @app.get("/")
    def root() -> dict[str, Any]:
        return {"name": "Ethan API", "ok": True, "docs": "/docs"}

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True}

    @app.post("/api/trading/connect")
    def trading_connect() -> dict[str, Any]:
        qmt_path = str(os.getenv("QMT_PATH") or "").strip()
        account_id = str(os.getenv("ACCOUNT_ID") or "").strip()
        if not qmt_path or not account_id:
            raise HTTPException(
                status_code=400,
                detail=err_detail(
                    "missing_env",
                    "缺少交易连接配置",
                    "请设置 QMT_PATH 与 ACCOUNT_ID，并确保 MiniQMT 已启动且登录完成",
                ),
            )

        trader = MiniQMTTrader(qmt_path=qmt_path, account_id=account_id)
        trader.connect()
        app.state.trader = trader
        return {"ok": True, "account_id": account_id}

    @app.post("/api/trading/disconnect")
    def trading_disconnect() -> dict[str, Any]:
        trader: MiniQMTTrader | None = app.state.trader
        if trader:
            trader.disconnect()
        app.state.trader = None
        return {"ok": True}

    @app.get("/api/trading/state")
    def trading_state() -> dict[str, Any]:
        trader: MiniQMTTrader | None = app.state.trader
        return {"connected": bool(trader and trader.connected)}

    @app.get("/api/trading/asset")
    def trading_asset() -> dict[str, Any]:
        trader: MiniQMTTrader | None = app.state.trader
        if not trader or not trader.connected:
            raise HTTPException(
                status_code=503,
                detail=err_detail("trader_not_connected", "交易连接未建立", "请先在连接页点击连接与校验"),
            )
        return trader.query_asset()

    @app.get("/api/trading/positions")
    def trading_positions() -> dict[str, Any]:
        trader: MiniQMTTrader | None = app.state.trader
        if not trader or not trader.connected:
            raise HTTPException(
                status_code=503,
                detail=err_detail("trader_not_connected", "交易连接未建立", "请先在连接页点击连接与校验"),
            )
        return {"items": trader.query_positions()}

    @app.get("/api/trading/orders")
    def trading_orders() -> dict[str, Any]:
        trader: MiniQMTTrader | None = app.state.trader
        if not trader or not trader.connected:
            raise HTTPException(
                status_code=503,
                detail=err_detail("trader_not_connected", "交易连接未建立", "请先在连接页点击连接与校验"),
            )
        return {"items": trader.query_orders()}

    @app.get("/api/trading/trades")
    def trading_trades() -> dict[str, Any]:
        trader: MiniQMTTrader | None = app.state.trader
        if not trader or not trader.connected:
            raise HTTPException(
                status_code=503,
                detail=err_detail("trader_not_connected", "交易连接未建立", "请先在连接页点击连接与校验"),
            )
        return {"items": trader.query_trades()}

    @app.get("/api/trading/events")
    def trading_events(limit: int = 200) -> dict[str, Any]:
        trader: MiniQMTTrader | None = app.state.trader
        if not trader:
            return {"items": []}
        items = trader.events[-min(max(int(limit), 1), 500) :]
        return {"items": items}

    @app.post("/api/executions")
    def executions_create(body: ExecutionTaskCreate) -> dict[str, Any]:
        if body.adv is None:
            try:
                df = load_stock_data(body.symbol, None, None)
                adv = float(df["volume"].mean())
            except Exception as e:
                raise HTTPException(
                    status_code=503,
                    detail=err_detail(
                        "data_unavailable",
                        "历史数据源不可用",
                        "请确认 MySQL 已启动，并配置 WUCAI_SQL_HOST/WUCAI_SQL_PORT/WUCAI_SQL_USERNAME/WUCAI_SQL_PASSWORD/WUCAI_SQL_DB",
                    ),
                )
        else:
            adv = float(body.adv)
        task = create_task(body, adv)
        app.state.store.put_task(task)
        return {"task": task.model_dump()}

    @app.get("/api/executions")
    def executions_list() -> dict[str, Any]:
        tasks = [t.model_dump() for t in app.state.store.list_tasks()]
        return {"items": tasks}

    @app.get("/api/executions/{task_id}")
    def executions_get(task_id: str) -> dict[str, Any]:
        task = app.state.store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        return {"task": task.model_dump()}

    @app.post("/api/executions/{task_id}/simulate")
    def executions_simulate(task_id: str, body: SimulationRequest) -> dict[str, Any]:
        task = app.state.store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        try:
            df = load_stock_data(task.symbol, None, None)
            daily = [df.iloc[i] for i in range(len(df))]
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=err_detail(
                    "data_unavailable",
                    "历史数据源不可用",
                    "请确认 MySQL 已启动，并配置 WUCAI_SQL_HOST/WUCAI_SQL_PORT/WUCAI_SQL_USERNAME/WUCAI_SQL_PASSWORD/WUCAI_SQL_DB",
                ),
            )
        res = simulate(task, daily, body)
        return {"items": res}

    @app.post("/api/executions/{task_id}/start")
    def executions_start(task_id: str, bg: BackgroundTasks) -> dict[str, Any]:
        task = app.state.store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        trader: MiniQMTTrader | None = app.state.trader
        if not trader or not trader.connected:
            raise HTTPException(
                status_code=503,
                detail=err_detail("trader_not_connected", "交易连接未建立", "请先在连接页点击连接与校验"),
            )
        loop = app.state.loop
        if loop is None:
            raise HTTPException(
                status_code=500,
                detail=err_detail("server_unavailable", "服务运行状态异常", "请重启后端服务"),
            )
        bg.add_task(start_execution, store=app.state.store, hub=app.state.hub, loop=loop, task_id=task_id, trader=trader)
        return {"ok": True}

    @app.post("/api/executions/{task_id}/stop")
    def executions_stop(task_id: str) -> dict[str, Any]:
        stopped = stop_execution(app.state.store, task_id)
        return {"ok": stopped}

    @app.websocket("/ws/executions/{task_id}")
    async def ws_exec(ws: WebSocket, task_id: str) -> None:
        channel = f"exec:{task_id}"
        await app.state.hub.connect(channel, ws)
        try:
            while True:
                await ws.receive_text()
        except Exception:
            pass
        finally:
            await app.state.hub.disconnect(channel, ws)

    @app.post("/api/rl/train")
    def rl_train(body: RLTrainRequest) -> dict[str, Any]:
        loop = app.state.loop
        if loop is None:
            raise HTTPException(
                status_code=500,
                detail=err_detail("server_unavailable", "服务运行状态异常", "请重启后端服务"),
            )
        try:
            run = start_train(store=app.state.store, hub=app.state.hub, loop=loop, req=body)
            return {"run": run.model_dump()}
        except Exception:
            raise HTTPException(
                status_code=503,
                detail=err_detail(
                    "data_unavailable",
                    "历史数据源不可用",
                    "请确认 MySQL 已启动，并配置 WUCAI_SQL_HOST/WUCAI_SQL_PORT/WUCAI_SQL_USERNAME/WUCAI_SQL_PASSWORD/WUCAI_SQL_DB",
                ),
            )

    @app.get("/api/rl/runs")
    def rl_runs() -> dict[str, Any]:
        return {"items": [r.model_dump() for r in app.state.store.list_rl_runs()]}

    @app.get("/api/rl/runs/{run_id}")
    def rl_run_get(run_id: str) -> dict[str, Any]:
        r = app.state.store.get_rl_run(run_id)
        if not r:
            raise HTTPException(status_code=404, detail="run not found")
        return {"run": r.model_dump()}

    @app.websocket("/ws/rl/{run_id}")
    async def ws_rl(ws: WebSocket, run_id: str) -> None:
        channel = f"rl:{run_id}"
        await app.state.hub.connect(channel, ws)
        try:
            while True:
                await ws.receive_text()
        except Exception:
            pass
        finally:
            await app.state.hub.disconnect(channel, ws)

    @app.post("/api/rl/backtest")
    def rl_backtest(body: RLBacktestRequest) -> dict[str, Any]:
        try:
            return backtest(body)
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=err_detail(
                    "data_unavailable",
                    "历史数据源不可用",
                    "请确认 MySQL 已启动，并配置 WUCAI_SQL_HOST/WUCAI_SQL_PORT/WUCAI_SQL_USERNAME/WUCAI_SQL_PASSWORD/WUCAI_SQL_DB",
                ),
            )

    @app.post("/api/agent/run")
    def agent_run(body: dict[str, Any]) -> dict[str, Any]:
        state = dict(body or {})
        result = app.state.graph.invoke(state)
        return {"result": result}

    return app


app = create_app()
