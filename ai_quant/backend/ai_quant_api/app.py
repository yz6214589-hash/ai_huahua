from __future__ import annotations

import os
import time

try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True), override=False)
except Exception:
    pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai_quant_api.api.agent import router as agent_router
from ai_quant_api.api.analysis_zoe import router as analysis_router
from ai_quant_api.api.console_ceo import router as console_router
from ai_quant_api.api.data_charles import router as data_router
from ai_quant_api.api.execution_ethan import router as execution_router
from ai_quant_api.api.health import router as health_router
from ai_quant_api.api.jobs import router as jobs_router
from ai_quant_api.api.reports import router as reports_router
from ai_quant_api.api.risk_kris import router as risk_router
from ai_quant_api.api.summary import router as summary_router
from ai_quant_api.api.trading_qmt import router as trading_router
from ai_quant_api.api.watchlist import router as watchlist_router
from ai_quant_api.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(title=settings.app_name, version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    rl_window_s = 10.0
    rl_max = 200
    try:
        rl_window_s = float(str(os.getenv("AI_QUANT_RATE_LIMIT_WINDOW_SECONDS", "10")).strip() or "10")
    except Exception:
        rl_window_s = 10.0
    try:
        rl_max = int(str(os.getenv("AI_QUANT_RATE_LIMIT_MAX", "200")).strip() or "200")
    except Exception:
        rl_max = 200
    rl_state: dict[str, tuple[float, int]] = {}

    @api.middleware("http")
    async def api_key_guard(request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        start, cnt = rl_state.get(ip, (now, 0))
        if now - start > rl_window_s:
            start, cnt = now, 0
        cnt += 1
        rl_state[ip] = (start, cnt)
        if rl_max > 0 and cnt > rl_max:
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁"})

        key = str(getattr(settings, "api_key", "") or "").strip()
        if key and request.url.path.startswith("/api") and request.url.path not in ("/api/health",):
            req_key = str(request.headers.get("x-api-key") or "").strip()
            if req_key != key:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Pragma"] = "no-cache"
        return resp

    @api.get("/")
    def root() -> dict[str, object]:
        return {"ok": True, "docs": "/docs", "health": "/api/health"}

    @api.get("/health")
    def health_alias() -> dict[str, bool]:
        return {"ok": True}

    api.include_router(health_router)
    api.include_router(summary_router)
    api.include_router(data_router)
    api.include_router(watchlist_router)
    api.include_router(jobs_router)
    api.include_router(reports_router)
    api.include_router(analysis_router)
    api.include_router(execution_router)
    api.include_router(trading_router)
    api.include_router(risk_router)
    api.include_router(console_router)
    api.include_router(agent_router)
    return api


app = create_app()
