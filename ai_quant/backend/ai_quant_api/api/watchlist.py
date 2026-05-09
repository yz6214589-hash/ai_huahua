from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ai_quant_api.services.charles.integration import (
    add_watchlist_item,
    delete_watchlist_item,
    get_watchlist,
    pin_watchlist_item,
    reorder_watchlist,
    search_stocks,
)

router = APIRouter(prefix="/api", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    stock_code: str


class WatchlistPinRequest(BaseModel):
    pinned: bool


class WatchlistReorderRequest(BaseModel):
    codes: list[str]



@router.get("/watchlist")
def watchlist_get() -> dict[str, object]:
    return get_watchlist()

@router.post("/watchlist")
def watchlist_add(req: WatchlistAddRequest) -> dict[str, Any]:
    return add_watchlist_item(req.stock_code)


@router.delete("/watchlist/{stock_code}")
def watchlist_delete(stock_code: str) -> dict[str, Any]:
    return delete_watchlist_item(stock_code)


@router.put("/watchlist/{stock_code}/pin")
def watchlist_pin(stock_code: str, req: WatchlistPinRequest) -> dict[str, Any]:
    return pin_watchlist_item(stock_code, bool(req.pinned))


@router.put("/watchlist/reorder")
def watchlist_reorder(req: WatchlistReorderRequest) -> dict[str, Any]:
    return reorder_watchlist(req.codes)



@router.get("/stocks")
def stocks_search(q: str = Query(default=""), limit: int = Query(default=20)) -> dict[str, object]:
    return search_stocks(q=q, limit=limit)
