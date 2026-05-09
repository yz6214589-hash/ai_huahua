from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Quant Unified API"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    api_key: str = ""


def get_settings() -> Settings:
    raw = os.getenv("AI_QUANT_CORS_ORIGINS", "http://localhost:5173")
    origins = tuple(x.strip() for x in raw.split(",") if x.strip())
    if any(x == "*" for x in origins):
        raise ValueError("AI_QUANT_CORS_ORIGINS 不允许包含 *")
    api_key = str(os.getenv("AI_QUANT_API_KEY", "")).strip()
    return Settings(cors_origins=origins or ("http://localhost:5173",), api_key=api_key)
