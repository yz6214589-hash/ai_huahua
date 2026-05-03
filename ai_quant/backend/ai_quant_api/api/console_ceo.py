from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ai_quant_api.services.ceo.integration import get_overview, get_status, trigger_morning

router = APIRouter(prefix="/api/console", tags=["console"])


@router.get("/status")
def console_status() -> dict[str, object]:
    return get_status()


@router.get("/overview")
def console_overview() -> dict[str, object]:
    return get_overview()


@router.post("/morning/trigger")
def console_trigger_morning(body: dict[str, Any]) -> dict[str, Any]:
    return trigger_morning(body)
