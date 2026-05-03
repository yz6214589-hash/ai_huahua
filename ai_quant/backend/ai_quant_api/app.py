from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_quant_api.api.agent import router as agent_router
from ai_quant_api.api.analysis_zoe import router as analysis_router
from ai_quant_api.api.console_ceo import router as console_router
from ai_quant_api.api.data_charles import router as data_router
from ai_quant_api.api.execution_ethan import router as execution_router
from ai_quant_api.api.health import router as health_router
from ai_quant_api.api.jobs import router as jobs_router
from ai_quant_api.api.risk_kris import router as risk_router
from ai_quant_api.api.summary import router as summary_router
from ai_quant_api.api.watchlist import router as watchlist_router
from ai_quant_api.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(title=settings.app_name, version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.include_router(health_router)
    api.include_router(summary_router)
    api.include_router(data_router)
    api.include_router(watchlist_router)
    api.include_router(jobs_router)
    api.include_router(analysis_router)
    api.include_router(execution_router)
    api.include_router(risk_router)
    api.include_router(console_router)
    api.include_router(agent_router)
    return api


app = create_app()
