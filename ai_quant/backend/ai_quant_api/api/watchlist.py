from __future__ import annotations

from fastapi import APIRouter, Query

from ai_quant_api.services.charles.integration import get_watchlist, search_stocks

router = APIRouter(prefix="/api", tags=["watchlist"])


@router.get("/watchlist")
def watchlist_get() -> dict[str, object]:
    return get_watchlist()


@router.get("/stocks")
def stocks_search(q: str = Query(default=""), limit: int = Query(default=20)) -> dict[str, object]:
    return search_stocks(q=q, limit=limit)
