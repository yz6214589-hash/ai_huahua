from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from services.qmt_gateway_client import request_json


router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.get("/state")
def trading_state() -> dict[str, Any]:
    try:
        return request_json("GET", "/api/trading/state")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/connect")
def trading_connect() -> dict[str, Any]:
    try:
        return request_json("POST", "/api/trading/connect", timeout_seconds=60)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/disconnect")
def trading_disconnect() -> dict[str, Any]:
    try:
        return request_json("POST", "/api/trading/disconnect")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/asset")
def trading_asset() -> dict[str, Any]:
    try:
        return request_json("GET", "/api/trading/asset")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/positions")
def trading_positions() -> dict[str, Any]:
    try:
        return request_json("GET", "/api/trading/positions")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/orders")
def trading_orders() -> dict[str, Any]:
    try:
        return request_json("GET", "/api/trading/orders")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/trades")
def trading_trades() -> dict[str, Any]:
    try:
        return request_json("GET", "/api/trading/trades")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/events")
def trading_events() -> dict[str, Any]:
    try:
        return request_json("GET", "/api/trading/events")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/buy")
def trading_buy(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return request_json("POST", "/api/trading/buy", body=body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/sell")
def trading_sell(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return request_json("POST", "/api/trading/sell", body=body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/cancel")
def trading_cancel(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return request_json("POST", "/api/trading/cancel", body=body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
