"""
QMT Gateway FastAPI 应用模块

提供基于 FastAPI 的 RESTful API 接口，用于与 MiniQMT 交易终端进行交互。
支持交易连接管理、账户查询、买卖下单、撤单、历史行情等核心功能。
所有接口均通过 X-API-Token 请求头进行身份验证。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from miniqmt_trader import MiniQMTTrader

logger = logging.getLogger("qmt_gateway")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


class BuySellRequest(BaseModel):
    stock_code: str
    volume: int = Field(ge=1)
    price: float = Field(default=0.0, ge=0.0)
    strategy_name: str = ""
    remark: str = ""


class CancelRequest(BaseModel):
    order_id: int


class KLineRequest(BaseModel):
    stock_code: str
    period: str = "1d"
    start_time: str = ""
    end_time: str = ""
    dividend_type: str = "front"
    fill_data: bool = True


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


def _ensure_connected(trader: MiniQMTTrader) -> None:
    """确保交易者已连接，未连接时自动尝试重连"""
    if trader.connected:
        return
    try:
        trader.connect()
        logger.info("自动重连成功")
    except Exception as e:
        logger.warning("自动重连失败: %s", e)
        raise HTTPException(status_code=503, detail=f"QMT 未连接且自动重连失败: {e}")


def create_app() -> FastAPI:
    api = FastAPI(title="AI Quant QMT Gateway", version="0.2.0")

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/api/trading/connect")
    def trading_connect(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        try:
            trader = _get_trader()
            ok = trader.connect()
            logger.info("连接请求: connected=%s account=%s", trader.connected, trader.account_id)
            return {"ok": bool(ok), "connected": trader.connected, "account_id": trader.account_id, "session_id": trader.session_id}
        except Exception as exc:
            logger.error("连接失败: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc))

    @api.post("/api/trading/disconnect")
    def trading_disconnect(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        trader.disconnect()
        logger.info("断开连接")
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
        _ensure_connected(trader)
        return {"asset": trader.query_asset()}

    @api.get("/api/trading/positions")
    def trading_positions(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        _ensure_connected(trader)
        return {"positions": trader.query_positions()}

    @api.get("/api/trading/orders")
    def trading_orders(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        _ensure_connected(trader)
        return {"orders": trader.query_orders()}

    @api.get("/api/trading/trades")
    def trading_trades(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        _ensure_connected(trader)
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
        _ensure_connected(trader)
        order_id = trader.buy(
            stock_code=body.stock_code,
            volume=int(body.volume),
            price=float(body.price or 0.0),
            strategy_name=str(body.strategy_name or ""),
            remark=str(body.remark or ""),
        )
        if order_id is None:
            raise HTTPException(status_code=400, detail="order rejected by risk check")
        logger.info("买入委托: %s %d股 order_id=%s", body.stock_code, body.volume, order_id)
        return {"order_id": int(order_id)}

    @api.post("/api/trading/sell")
    def trading_sell(body: BuySellRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        _ensure_connected(trader)
        order_id = trader.sell(
            stock_code=body.stock_code,
            volume=int(body.volume),
            price=float(body.price or 0.0),
            strategy_name=str(body.strategy_name or ""),
            remark=str(body.remark or ""),
        )
        if order_id is None:
            raise HTTPException(status_code=400, detail="order rejected by risk check")
        logger.info("卖出委托: %s %d股 order_id=%s", body.stock_code, body.volume, order_id)
        return {"order_id": int(order_id)}

    @api.post("/api/trading/cancel")
    def trading_cancel(body: CancelRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        _ensure_connected(trader)
        order_id = trader.cancel(int(body.order_id))
        if order_id is None:
            raise HTTPException(status_code=400, detail="cancel rejected")
        logger.info("撤单: order_id=%s", order_id)
        return {"order_id": int(order_id)}

    @api.post("/api/trading/cancel_all")
    def trading_cancel_all(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        _ensure_connected(trader)
        canceled = trader.cancel_all()
        logger.info("全部撤单: count=%d ids=%s", len(canceled), canceled)
        return {"canceled_count": len(canceled), "canceled_ids": canceled}

    @api.post("/api/historical/kline")
    def historical_kline(body: KLineRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        _check_token(x_api_token)
        trader = _get_trader()
        stock_code = str(body.stock_code or "").strip()
        period = str(body.period or "1d").strip()
        start_time = str(body.start_time or "").strip()
        end_time = str(body.end_time or "").strip()
        dividend_type = str(body.dividend_type or "front").strip()
        fill_data = bool(body.fill_data)

        try:
            trader.download_history_data(
                stock_code=stock_code,
                period=period,
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as e:
            logger.warning("下载历史数据失败: %s %s", stock_code, e)

        time.sleep(1)

        try:
            raw = trader.get_market_data_ex(
                stock_list=[stock_code],
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=-1,
                dividend_type=dividend_type,
                fill_data=fill_data,
            )
        except Exception as e:
            logger.error("获取K线数据失败: %s %s", stock_code, e)
            return {"rows": [], "columns": [], "error": str(e)}

        if not raw or stock_code not in raw:
            return {"rows": [], "columns": []}

        df = raw[stock_code]
        if df is None or df.empty:
            return {"rows": [], "columns": []}

        import pandas as pd

        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                pass

        out_rows = []
        for idx, row in df.iterrows():
            date_str = ""
            if hasattr(idx, "strftime"):
                date_str = idx.strftime("%Y%m%d")
            else:
                date_str = str(idx)

            out_rows.append({
                "date": date_str,
                "open": float(row.get("open", 0) or 0),
                "high": float(row.get("high", 0) or 0),
                "low": float(row.get("low", 0) or 0),
                "close": float(row.get("close", 0) or 0),
                "volume": int(row.get("volume", 0) or 0),
                "amount": float(row.get("amount", 0) or 0),
            })

        return {"rows": out_rows, "columns": ["date", "open", "high", "low", "close", "volume", "amount"]}

    return api


app = create_app()
