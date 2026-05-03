from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Quant Unified API"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)


def get_settings() -> Settings:
    raw = os.getenv("AI_QUANT_CORS_ORIGINS", "http://localhost:5173")
    origins = tuple(x.strip() for x in raw.split(",") if x.strip())
    return Settings(cors_origins=origins or ("http://localhost:5173",))
