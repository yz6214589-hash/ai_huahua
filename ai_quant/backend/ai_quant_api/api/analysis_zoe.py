from fastapi import APIRouter

from ai_quant_api.services.zoe.integration import get_sample_codes, get_signals, get_status

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/status")
def analysis_status() -> dict[str, object]:
    return get_status()


@router.get("/stocks/sample")
def analysis_stocks_sample(limit: int = 50) -> dict[str, object]:
    return get_sample_codes(limit=limit)


@router.get("/signals")
def analysis_signals(stock_code: str, start: str, end: str) -> dict[str, object]:
    return get_signals(stock_code=stock_code, start=start, end=end)
