from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from src.backend.risk import approve, audit, status
from src.backend..infra.storage.logging_service import get_logger

logger = get_logger("risk")

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


@router.get("/status")
def risk_status() -> dict[str, object]:
    logger.info("风控状态查询", extra={})
    return status()


@router.post("/approve")
def risk_approve(body: dict[str, Any]) -> dict[str, Any]:
    logger.info("风控审批请求", extra={
        "stock_code": body.get("stockCode"),
        "qty": body.get("qty"),
        "side": body.get("side")
    })
    try:
        result = approve(body)
        logger.info("风控审批成功", extra={
            "stock_code": body.get("stockCode"),
            "decision": result.get("decision")
        })
        return result
    except Exception as exc:
        logger.error("风控审批失败", extra={
            "stock_code": body.get("stockCode"),
            "error": str(exc)
        })
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/audit")
def risk_audit(last_n: int = 200) -> dict[str, Any]:
    logger.info("风控审计查询", extra={
        "last_n": last_n
    })
    return audit(last_n)
