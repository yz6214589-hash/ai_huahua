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
    """
    获取必需的环境变量值

    Args:
        name: 环境变量名称

    Returns:
        环境变量的值（已去除首尾空白）

    Raises:
        RuntimeError: 当环境变量未设置或值为空时抛出
    """
    v = str(os.getenv(name, "")).strip()
    if not v:
        raise RuntimeError(f"missing env: {name}")
    return v


def _env_int(name: str, default: int) -> int:
    """
    获取整数类型的环境变量值

    Args:
        name: 环境变量名称
        default: 默认值

    Returns:
        解析后的整数值，解析失败时返回默认值
    """
    raw = str(os.getenv(name, "")).strip()
    try:
        return int(raw) if raw else int(default)
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    """
    获取浮点数类型的环境变量值

    Args:
        name: 环境变量名称
        default: 默认值

    Returns:
        解析后的浮点数值，解析失败时返回默认值
    """
    raw = str(os.getenv(name, "")).strip()
    try:
        return float(raw) if raw else float(default)
    except Exception:
        return float(default)


def _check_token(x_api_token: str | None) -> None:
    """
    验证 API 请求令牌

    从环境变量 QMT_API_TOKEN 获取配置的令牌值，
    并与请求头中的 X-API-Token 进行比对验证。

    Args:
        x_api_token: 请求头中的 API 令牌

    Raises:
        HTTPException: 当令牌不匹配时抛出 401 异常
    """
    required = str(os.getenv("QMT_API_TOKEN", "")).strip()
    if not required:
        return
    if str(x_api_token or "").strip() != required:
        raise HTTPException(status_code=401, detail="invalid token")


_TRADER: MiniQMTTrader | None = None


def _get_trader() -> MiniQMTTrader:
    """
    获取或创建全局 MiniQMTTrader 实例

    使用单例模式管理交易者实例，确保整个应用生命周期内
    只有一个活跃的交易连接。通过环境变量配置 QMT 终端路径、
    账户信息及风控参数。

    Returns:
        MiniQMTTrader: 配置好的交易者实例
    """
    global _TRADER
    if _TRADER is not None:
        return _TRADER

    # 从环境变量加载 QMT 配置
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
    """
    创建并配置 FastAPI 应用实例

    定义所有交易相关的 API 端点，包括：
    - 健康检查
    - 连接管理（连接/断开）
    - 账户状态查询
    - 持仓、订单、成交查询
    - 买卖下单与撤单

    Returns:
        FastAPI: 配置完成的 FastAPI 应用实例
    """
    api = FastAPI(title="AI Quant QMT Gateway", version="0.1.0")

    @api.get("/health")
    def health() -> dict[str, str]:
        """健康检查接口，用于验证服务是否正常运行"""
        return {"status": "ok"}

    @api.post("/api/trading/connect")
    def trading_connect(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        连接到 MiniQMT 交易终端

        初始化并建立与 QMT 终端的交易连接，订阅账户信息。
        连接成功后返回账户标识和会话信息。
        """
        _check_token(x_api_token)
        try:
            trader = _get_trader()
            ok = trader.connect()
            return {"ok": bool(ok), "connected": trader.connected, "account_id": trader.account_id, "session_id": trader.session_id}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @api.post("/api/trading/disconnect")
    def trading_disconnect(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        断开与 MiniQMT 交易终端的连接

        停止交易者并清理连接状态。
        """
        _check_token(x_api_token)
        trader = _get_trader()
        trader.disconnect()
        return {"ok": True, "connected": trader.connected}

    @api.get("/api/trading/state")
    def trading_state(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        获取交易终端当前状态

        返回连接状态、账户信息、会话 ID 以及最近的事件日志。
        """
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
        """
        查询账户资产信息

        返回总资产、现金余额、市值和冻结资金等数据。
        """
        _check_token(x_api_token)
        trader = _get_trader()
        return {"asset": trader.query_asset()}

    @api.get("/api/trading/positions")
    def trading_positions(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        查询当前持仓信息

        返回所有当前持有的股票及其数量、成本价等详细信息。
        """
        _check_token(x_api_token)
        trader = _get_trader()
        return {"positions": trader.query_positions()}

    @api.get("/api/trading/orders")
    def trading_orders(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        查询当日订单记录

        返回所有当日提交的委托订单及其成交状态。
        """
        _check_token(x_api_token)
        trader = _get_trader()
        return {"orders": trader.query_orders()}

    @api.get("/api/trading/trades")
    def trading_trades(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        查询当日成交记录

        返回所有当日成交的明细信息。
        """
        _check_token(x_api_token)
        trader = _get_trader()
        return {"trades": trader.query_trades()}

    @api.get("/api/trading/events")
    def trading_events(x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        获取最近的交易事件日志

        返回最近 200 条事件记录，包括订单推送、成交回报等实时信息。
        """
        _check_token(x_api_token)
        trader = _get_trader()
        return {"events": trader.events[-200:]}

    @api.post("/api/trading/buy")
    def trading_buy(body: BuySellRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        买入股票

        根据请求参数提交买入订单，支持限价单和市价单。
        订单会经过风险检查，包括持仓数量限制和单笔金额限制。

        Args:
            body: 包含股票代码、数量、价格等信息的请求体

        Returns:
            包含订单 ID 的响应

        Raises:
            HTTPException: 当订单被拒绝时抛出 400 异常
        """
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
        """
        卖出股票

        根据请求参数提交卖出订单，支持限价单和市价单。
        卖出前会检查持仓数量是否足够。

        Args:
            body: 包含股票代码、数量、价格等信息的请求体

        Returns:
            包含订单 ID 的响应

        Raises:
            HTTPException: 当订单被拒绝时抛出 400 异常
        """
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
        """
        撤销指定订单

        根据订单 ID 撤销未完全成交的委托。

        Args:
            body: 包含订单 ID 的请求体

        Returns:
            包含订单 ID 的响应

        Raises:
            HTTPException: 当撤单失败时抛出 400 异常
        """
        _check_token(x_api_token)
        trader = _get_trader()
        order_id = trader.cancel(int(body.order_id))
        if order_id is None:
            raise HTTPException(status_code=400, detail="cancel rejected")
        return {"order_id": int(order_id)}

    # ─────────── 历史行情接口 ───────────

    @api.post("/api/historical/kline")
    def historical_kline(body: KLineRequest, x_api_token: str | None = Header(default=None)) -> dict[str, Any]:
        """
        下载并获取股票历史K线数据。

        先将数据下载到 QMT 本地缓存，再读取返回 DataFrame 格式的 OHLCV 数据。

        Args:
            body: 包含 stock_code/period/start_time/end_time 等参数

        Returns:
            包含 rows（列表）和 columns（字段名）的 K 线数据
        """
        _check_token(x_api_token)
        trader = _get_trader()

        trader.download_history_data(
            stock_code=str(body.stock_code or "").strip(),
            period=str(body.period or "1d").strip(),
            start_time=str(body.start_time or "").strip(),
            end_time=str(body.end_time or "").strip(),
        )

        import time as _time
        _time.sleep(1)

        raw = trader.get_market_data(
            stock_list=[str(body.stock_code or "").strip()],
            period=str(body.period or "1d").strip(),
            start_time=str(body.start_time or "").strip(),
            end_time=str(body.end_time or "").strip(),
            count=-1,
            dividend_type=str(body.dividend_type or "front").strip(),
            fill_data=bool(body.fill_data),
        )

        if not raw:
            return {"rows": [], "columns": []}

        close_df = raw.get("close")
        if close_df is None or body.stock_code not in close_df.index:
            return {"rows": [], "columns": []}

        dates = [str(int(d)) for d in close_df.columns.tolist()]
        stock_code = str(body.stock_code or "").strip()

        rows = []
        for field in ["open", "high", "low", "close", "volume", "amount"]:
            series = raw.get(field)
            if series is not None and stock_code in series.index:
                rows.append({str(d): series.loc[stock_code, d] if d in series.columns else None for d in dates})
            else:
                rows.append({d: None for d in dates})

        columns = ["date"] + [f for f in ["open", "high", "low", "close", "volume", "amount"] if rows and rows[0].get("close") is not None or True]
        out_rows = []
        for i, d in enumerate(dates):
            row = {"date": d}
            for j, col in enumerate(["open", "high", "low", "close", "volume", "amount"]):
                if j < len(rows):
                    row[col] = rows[j].get(d)
            out_rows.append(row)

        return {"rows": out_rows, "columns": ["date", "open", "high", "low", "close", "volume"]}

    return api


app = create_app()

