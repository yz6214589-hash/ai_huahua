"""
QMT Gateway FastAPI 应用模块

提供基于 FastAPI 的 RESTful API 接口，用于与 MiniQMT 交易终端进行交互。
支持交易连接管理、账户查询、买卖下单、撤单等核心功能。
所有接口均通过 X-API-Token 请求头进行身份验证。
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from miniqmt_trader import MiniQMTTrader


class BuySellRequest(BaseModel):
    """买入或卖出股票的请求数据模型"""
    stock_code: str
    volume: int = Field(ge=1)
    price: float = Field(default=0.0, ge=0.0)
    strategy_name: str = ""
    remark: str = ""


class CancelRequest(BaseModel):
    """撤销订单的请求数据模型"""
    order_id: int


class KLineRequest(BaseModel):
    """查询历史K线的请求模型"""
    stock_code: str
    period: str = "1d"
    start_time: str = ""
    end_time: str = ""
    dividend_type: str = "front"
    fill_data: bool = True


def _must_env(name: str) -> str:
    """获取必需的环境变量值。"""
    v = str(os.getenv(name, "")).strip()
    if not v:
        raise RuntimeError(f"missing env: {name}")
    return v


def _env_int(name: str, default: int) -> int:
    """获取整数类型的环境变量值。"""
    raw = str(os.getenv(name, "")).strip()
    try:
        return int(raw) if raw else int(default)
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    """获取浮点数类型的环境变量值。"""
    raw = str(os.getenv(name, "")).strip()
    try:
        return float(raw) if raw else float(default)
    except Exception:
        return float(default)


def _check_token(x_api_token: str | None) -> None:
    """验证 API 请求令牌。"""
    required = str(os.getenv("QMT_API_TOKEN", "")).strip()
    if not required:
        return
    if str(x_api_token or "").strip() != required:
        raise HTTPException(status_code=401, detail="invalid token")


_TRADER: MiniQMTTrader | None = None


def _get_trader() -> MiniQMTTrader:
    """获取或创建全局 MiniQMTTrader 实例。"""
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
    """创建并配置 FastAPI 应用实例。"""
    api = FastAPI(title="AI Quant QMT Gateway", version="0.1.0")

    @api.get("/health")
    def health() -> dict[str, str]:
        """健康检查接口。"""
        return {"status": "ok"}

    @api.post("/api/trading/connect")
    def trading_connect(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """连接到 MiniQMT 交易终端。"""
        _check_token(x_api_token)
        try:
            trader = _get_trader()
            ok = trader.connect()
            return {"ok": bool(ok), "connected": trader.connected, "account_id": trader.account_id, "session_id": trader.session_id}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @api.post("/api/trading/disconnect")
    def trading_disconnect(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """断开与 MiniQMT 交易终端的连接。"""
        _check_token(x_api_token)
        trader = _get_trader()
        trader.disconnect()
        return {"ok": True, "connected": trader.connected}

    @api.get("/api/trading/state")
    def trading_state(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """获取交易终端当前状态。"""
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
        """查询账户资产信息。"""
        _check_token(x_api_token)
        trader = _get_trader()
        return {"asset": trader.query_asset()}

    @api.get("/api/trading/positions")
    def trading_positions(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """查询当前持仓信息。"""
        _check_token(x_api_token)
        trader = _get_trader()
        return {"positions": trader.query_positions()}

    @api.get("/api/trading/orders")
    def trading_orders(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """查询当日订单记录。"""
        _check_token(x_api_token)
        trader = _get_trader()
        return {"orders": trader.query_orders()}

    @api.get("/api/trading/trades")
    def trading_trades(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """查询当日成交记录。"""
        _check_token(x_api_token)
        trader = _get_trader()
        return {"trades": trader.query_trades()}

    @api.get("/api/trading/events")
    def trading_events(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """获取最近的交易事件日志。"""
        _check_token(x_api_token)
        trader = _get_trader()
        return {"events": trader.events[-200:]}

    @api.post("/api/trading/buy")
    def trading_buy(body: BuySellRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """买入股票。"""
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
        """卖出股票。"""
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
        """撤销指定订单。"""
        _check_token(x_api_token)
        trader = _get_trader()
        order_id = trader.cancel(int(body.order_id))
        if order_id is None:
            raise HTTPException(status_code=400, detail="cancel rejected")
        return {"order_id": int(order_id)}

    @api.post("/api/historical/kline")
    def historical_kline(body: KLineRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        下载并获取股票历史K线数据。

        直接使用 xtquant.xtdata，不依赖 MiniQMT 连接状态。
        """
        _check_token(x_api_token)

        import time as _time

        try:
            from xtquant import xtdata
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"xtquant import failed: {e}")

        code = str(body.stock_code or "").strip()
        period = str(body.period or "1d").strip()
        start_time = str(body.start_time or "").strip()
        end_time = str(body.end_time or "").strip()
        dividend_type = str(body.dividend_type or "front").strip()
        fill_data = bool(body.fill_data)

        try:
            xtdata.download_history_data(
                stock_code=code,
                period=period,
                start_time=start_time,
                end_time=end_time,
            )
            _time.sleep(1)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"download failed: {e}")

        try:
            raw = xtdata.get_market_data(
                stock_list=[code],
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=-1,
                dividend_type=dividend_type,
                fill_data=fill_data,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"get_market_data failed: {e}")

        if not raw:
            return {"rows": [], "columns": []}

        close_df = raw.get("close")
        if close_df is None or code not in close_df.index:
            return {"rows": [], "columns": []}

        dates = [str(int(d)) for d in close_df.columns.tolist()]

        field_list = ["open", "high", "low", "close", "volume", "amount"]
        field_data: dict[str, dict[str, Any]] = {}
        for field in field_list:
            series = raw.get(field)
            if series is not None and code in series.index:
                field_data[field] = {str(d): series.loc[code, d] if d in series.columns else None for d in dates}
            else:
                field_data[field] = {d: None for d in dates}

        out_rows = []
        for d in dates:
            row: dict[str, Any] = {"date": d}
            for field in field_list:
                row[field] = field_data[field].get(d)
            out_rows.append(row)

        return {"rows": out_rows, "columns": ["date"] + field_list}

    return api


app = create_app()
