from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def validate_mainforce_params(params: dict[str, Any]) -> dict[str, int]:
    p = params or {}
    allowed = {"n_samples_per_class", "seed", "n_ticks", "window"}
    unknown = [k for k in p.keys() if k not in allowed]
    if unknown:
        raise HTTPException(status_code=400, detail={"error": "invalid_params", "fields": {"params": f"unknown_keys: {unknown}"}})

    def as_int(key: str, default: int) -> int:
        v = p.get(key, default)
        if v is None:
            return int(default)
        try:
            return int(v)
        except Exception:
            raise HTTPException(status_code=400, detail={"error": "invalid_params", "fields": {key: "not_int"}})

    n_samples_per_class = as_int("n_samples_per_class", 200)
    seed = as_int("seed", 42)
    n_ticks = as_int("n_ticks", 300)
    window = as_int("window", 50)

    errors: dict[str, str] = {}
    if n_samples_per_class < 1 or n_samples_per_class > 500:
        errors["n_samples_per_class"] = "range: 1..500"
    if n_ticks < 30 or n_ticks > 1000:
        errors["n_ticks"] = "range: 30..1000"
    if window < 5 or window > 300:
        errors["window"] = "range: 5..300"
    if window >= n_ticks:
        errors["window"] = "must_be_lt_n_ticks"
    if errors:
        raise HTTPException(status_code=400, detail={"error": "invalid_params", "fields": errors})

    return {
        "n_samples_per_class": int(n_samples_per_class),
        "seed": int(seed),
        "n_ticks": int(n_ticks),
        "window": int(window),
    }

