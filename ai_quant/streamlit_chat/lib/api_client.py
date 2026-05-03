from __future__ import annotations

import os
from typing import Any

import requests


def run_agent(user_input: str) -> dict[str, Any]:
    base = os.getenv("AI_QUANT_API_BASE", "http://localhost:8000")
    resp = requests.post(
        f"{base}/api/agent/run",
        json={"input": user_input},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
