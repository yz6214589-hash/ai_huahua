# -*- coding: utf-8 -*-
"""QMT 交易终端 API 路由模块

提供交易终端的 RESTful 接口，通过 QMT Gateway 客户端与腾讯云上的 MiniQMT 交互。
支持多账户切换，通过 account_type 查询参数指定目标账户。
"""
from __future__ import annotations

import logging
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


@router.get("/accounts")
def trading_accounts() -> dict[str, Any]:
    try:
        return _get_accounts()
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/connect")
def trading_connect(
    account_type: str | None = Query(default=None, description="账户类型，如 国金模拟、光大实盘"),
) -> dict[str, Any]:
    try:
        return _connect(account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/disconnect")
def trading_disconnect(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _disconnect(account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/state")
def trading_state(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _get_state(account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/asset")
def trading_asset(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _get_asset(account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/positions")
def trading_positions(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _get_positions(account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/orders")
def trading_orders(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _get_orders(account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/trades")
def trading_trades(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _get_trades(account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/events")
def trading_events(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _get_events(account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/buy")
def trading_buy(
    body: BuySellRequest,
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _buy(
            stock_code=body.stock_code, volume=body.volume, price=body.price,
            strategy_name=body.strategy_name, remark=body.remark,
            account_type=account_type,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/sell")
def trading_sell(
    body: BuySellRequest,
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _sell(
            stock_code=body.stock_code, volume=body.volume, price=body.price,
            strategy_name=body.strategy_name, remark=body.remark,
            account_type=account_type,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/cancel")
def trading_cancel(
    body: CancelRequest,
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _cancel(order_id=body.order_id, account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/cancel_all")
def trading_cancel_all(
    account_type: str | None = Query(default=None, description="账户类型"),
) -> dict[str, Any]:
    try:
        return _cancel_all(account_type=account_type)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
