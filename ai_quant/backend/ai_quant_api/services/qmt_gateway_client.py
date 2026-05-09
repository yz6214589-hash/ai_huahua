from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


_DOTENV_LOADED = False


def _load_dotenv_once() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def _base() -> str:
    _load_dotenv_once()
    v = str(os.getenv("AI_QUANT_QMT_GATEWAY_BASE", "")).strip()
    if not v:
        raise RuntimeError("missing env: AI_QUANT_QMT_GATEWAY_BASE")
    return v.rstrip("/")


def _env_timeout(name: str, default: float) -> float:
    _load_dotenv_once()
    raw = str(os.getenv(name, "")).strip()
    try:
        v = float(raw) if raw else float(default)
        return v if v > 0 else float(default)
    except Exception:
        return float(default)



def _token_header() -> dict[str, str]:
    _load_dotenv_once()
    token = str(os.getenv("AI_QUANT_QMT_GATEWAY_TOKEN", "")).strip()
    if not token:
        return {}
    return {"X-API-Token": token}

def request_json(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    url = f"{_base()}{path}"
    headers = {"Content-Type": "application/json", **_token_header()}

    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, method=method.upper(), headers=headers)
    timeout = float(timeout_seconds) if timeout_seconds is not None else _env_timeout("AI_QUANT_QMT_GATEWAY_TIMEOUT", 5.0)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
            detail = raw.decode("utf-8", errors="ignore")
        except Exception:
            detail = str(e)
        raise RuntimeError(detail)
    except Exception as e:
        raise RuntimeError(f"{type(e).__name__}: {e}")
