# -*- coding: utf-8 -*-
"""QMT 交易终端 API 路由模块

提供交易终端的 RESTful 接口，通过 QMT Gateway 客户端与腾讯云上的 MiniQMT 交互。
支持多账户切换，通过 account_type 查询参数指定目标账户。
"""
from __future__ import annotations

import functools
import logging
import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from infra.qmt_gateway_client import (
    buy as _buy,
    cancel as _cancel,
    cancel_all as _cancel_all,
    connect as _connect,
    disconnect as _disconnect,
    get_accounts as _get_accounts,
    get_asset as _get_asset,
    get_events as _get_events,
    get_orders as _get_orders,
    get_positions as _get_positions,
    get_state as _get_state,
    get_trades as _get_trades,
    sell as _sell,
)


class BuySellRequest(BaseModel):
    """买入/卖出请求体"""
    stock_code: str = Field(..., description="股票代码")
    volume: int = Field(..., description="委托数量")
    price: float = Field(0.0, description="委托价格，0 表示市价")
    strategy_name: str = Field("", description="策略名称")
    remark: str = Field("", description="备注")


class CancelRequest(BaseModel):
    """撤单请求体"""
    order_id: int = Field(..., description="委托订单 ID")

logger = logging.getLogger("trading_qmt")

router = APIRouter(prefix="/api/v1/trading", tags=["trading"])


def handle_qmt_connection_error(func):
    """装饰器：统一处理 QMT Gateway ConnectionError，转换为 HTTP 503 响应"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
    return wrapper


def _filter_by_date(items: list[dict[str, Any]], time_field: str, start_date: str = "", end_date: str = "") -> list[dict[str, Any]]:
    """按日期范围过滤列表数据（在本地执行，无需修改远程 Gateway）"""
    if not start_date and not end_date:
        return items
    sd = start_date.replace("-", "") if start_date else ""
    ed = end_date.replace("-", "") if end_date else ""
    result: list[dict[str, Any]] = []
    for item in items:
        ts = item.get(time_field)
        # 有日期筛选条件时，无有效时间戳的记录不通过
        if ts is None or ts == "" or ts == 0:
            continue
        ts_str = str(ts).strip()
        if not ts_str:
            continue

        raw = ts_str
        if raw.isdigit():
            if len(raw) == 10:
                # Unix 时间戳（秒），转换为 YYYYMMDD
                try:
                    dt = datetime.datetime.fromtimestamp(int(raw))
                    date_part = dt.strftime("%Y%m%d")
                except (OSError, ValueError, OverflowError):
                    continue
            else:
                # YYYYMMDDHHMMSS 或 YYYYMMDD 格式，取前8位
                date_part = raw[:8]
        else:
            # 可能是 "2026-06-02 13:34:03" 格式
            date_part = raw[:10].replace("-", "")[:8]

        if sd and date_part < sd:
            continue
        if ed and date_part > ed:
            continue
        result.append(item)
    return result


@router.get("/accounts")
@handle_qmt_connection_error
def trading_accounts() -> dict[str, Any]:
    return _get_accounts()


@router.post("/connect")
@handle_qmt_connection_error
def trading_connect(
    account_type: str | None = Query(default=None, description="账户类型，如 国金模拟、光大实盘"),
) -> dict[str, Any]:
    return _connect(account_type=account_type)


@router.post("/disconnect")
@handle_qmt_connection_error
def trading_disconnect(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    return _disconnect(account_type=account_type)


@router.get("/state")
@handle_qmt_connection_error
def trading_state(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    return _get_state(account_type=account_type)


@router.get("/asset")
@handle_qmt_connection_error
def trading_asset(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    return _get_asset(account_type=account_type)

@router.get("/positions")
@handle_qmt_connection_error
def trading_positions(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    return _get_positions(account_type=account_type)


@router.get("/orders")
@handle_qmt_connection_error
def trading_orders(
    account_type: str | None = Query(default=None, description="账户类型"),
    start_date: str | None = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="结束日期 YYYY-MM-DD"),
) -> dict[str, Any]:
    data = _get_orders(account_type=account_type)
    orders = data.get("orders", [])
    orders = _filter_by_date(orders, "order_time", start_date or "", end_date or "")
    return {"orders": orders, "account_type": data.get("account_type", account_type)}

@router.get("/trades")
@handle_qmt_connection_error
def trading_trades(
    account_type: str | None = Query(default=None, description="账户类型"),
    start_date: str | None = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="结束日期 YYYY-MM-DD"),
) -> dict[str, Any]:
    data = _get_trades(account_type=account_type)
    trades = data.get("trades", [])
    trades = _filter_by_date(trades, "traded_time", start_date or "", end_date or "")
    return {"trades": trades, "account_type": data.get("account_type", account_type)}

@router.get("/events")
@handle_qmt_connection_error
def trading_events(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    return _get_events(account_type=account_type)


@router.post("/buy")
@handle_qmt_connection_error
def trading_buy(
    body: BuySellRequest,
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    return _buy(
        stock_code=body.stock_code, volume=body.volume, price=body.price,
        strategy_name=body.strategy_name, remark=body.remark,
        account_type=account_type,
    )

@router.post("/sell")
@handle_qmt_connection_error
def trading_sell(
    body: BuySellRequest,
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    return _sell(
        stock_code=body.stock_code, volume=body.volume, price=body.price,
        strategy_name=body.strategy_name, remark=body.remark,
        account_type=account_type,
    )

@router.post("/cancel")
@handle_qmt_connection_error
def trading_cancel(
    body: CancelRequest,
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    return _cancel(order_id=body.order_id, account_type=account_type)

@router.post("/cancel_all")
@handle_qmt_connection_error
def trading_cancel_all(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    return _cancel_all(account_type=account_type)
