from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from miniqmt_trader import MiniQMTTrader


class BuySellRequest(BaseModel):
    stock_code: str
    volume: int = Field(ge=1)
    price: float = Field(default=0.0, ge=0.0)
    strategy_name: str = ""
    remark: str = ""


class CancelRequest(BaseModel):
    order_id: int


def _must_env(name: str) -> str:
    v = str(os.getenv(name, "")).strip()
    if not v:
        raise RuntimeError(f"missing env: {name}")
    return v


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    try:
        return int(raw) if raw else int(default)
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "")).strip()
    try:
        return float(raw) if raw else float(default)
    except Exception:
        return float(default)


def _check_token(x_api_token: str | None) -> None:
    required = str(os.getenv("QMT_API_TOKEN", "")).strip()
    if not required:
        return
    if str(x_api_token or "").strip() != required:
        raise HTTPException(status_code=401, detail="invalid token")


_TRADER: MiniQMTTrader | None = None


def _get_trader() -> MiniQMTTrader:
    global _TRADER
    if _TRADER is not None:
        return _TRADER

    qmt_path = _must_env("QMT_PATH")
    account_id = _must_env("ACCOUNT_ID")
    session_id = _env_int("QMT_SESSION_ID", 0) or None
    max_positions = _env_int("QMT_MAX_POSITIONS", 10)
    max_order_amount = _env_float("QMT_MAX_ORDER_AMOUNT", 500000.0)
    _TRADER = MiniQMTTrader(
        qmt_path=qmt_path,
        account_id=account_id,
        session_id=session_id,
        max_positions=max_positions,
        max_order_amount=max_order_amount,
    )
    return _TRADER


def create_app() -> FastAPI:
    api = FastAPI(title="AI Quant QMT Gateway", version="0.1.0")

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/api/trading/connect")
    def trading_connect(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        try:
            trader = _get_trader()
            ok = trader.connect()
            return {"ok": bool(ok), "connected": trader.connected, "account_id": trader.account_id, "session_id": trader.session_id}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @api.post("/api/trading/disconnect")
    def trading_disconnect(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        trader.disconnect()
        return {"ok": True, "connected": trader.connected}

    @api.get("/api/trading/state")
    def trading_state(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        events = trader.events
        last = events[-1] if events else None
        return {
            "connected": trader.connected,
            "account_id": trader.account_id,
            "session_id": trader.session_id,
            "events_count": len(events),
            "last_event": last,
        }

    @api.get("/api/trading/asset")
    def trading_asset(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        return {"asset": trader.query_asset()}

    @api.get("/api/trading/positions")
    def trading_positions(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        return {"positions": trader.query_positions()}

    @api.get("/api/trading/orders")
    def trading_orders(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        return {"orders": trader.query_orders()}

    @api.get("/api/trading/trades")
    def trading_trades(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        return {"trades": trader.query_trades()}

    @api.get("/api/trading/events")
    def trading_events(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        return {"events": trader.events[-200:]}

    @api.post("/api/trading/buy")
    def trading_buy(body: BuySellRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        order_id = trader.buy(
            stock_code=body.stock_code,
            volume=int(body.volume),
            price=float(body.price or 0.0),
            strategy_name=str(body.strategy_name or ""),
            remark=str(body.remark or ""),
        )
        if order_id is None:
            raise HTTPException(status_code=400, detail="order rejected")
        return {"order_id": int(order_id)}

    @api.post("/api/trading/sell")
    def trading_sell(body: BuySellRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        order_id = trader.sell(
            stock_code=body.stock_code,
            volume=int(body.volume),
            price=float(body.price or 0.0),
            strategy_name=str(body.strategy_name or ""),
            remark=str(body.remark or ""),
        )
        if order_id is None:
            raise HTTPException(status_code=400, detail="order rejected")
        return {"order_id": int(order_id)}

    @api.post("/api/trading/cancel")
    def trading_cancel(body: CancelRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        order_id = trader.cancel(int(body.order_id))
        if order_id is None:
            raise HTTPException(status_code=400, detail="cancel rejected")
        return {"order_id": int(order_id)}

    return api


app = create_app()

