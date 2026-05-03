from fastapi import APIRouter

from ai_quant_api.services.charles.integration import get_summary

router = APIRouter(prefix="/api", tags=["summary"])


@router.get("/summary")
def summary() -> dict[str, dict[str, object]]:
    return get_summary()
