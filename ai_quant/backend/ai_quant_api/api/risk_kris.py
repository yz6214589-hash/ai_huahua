from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ai_quant_api.services.kris.integration import approve, audit, status

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/status")
def risk_status() -> dict[str, object]:
    return status()


@router.post("/approve")
def risk_approve(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return approve(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/audit")
def risk_audit(last_n: int = 200) -> dict[str, Any]:
    return audit(last_n)
