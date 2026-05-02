from __future__ import annotations

import os
import threading
import time
from typing import Any

_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None
_CACHE_TS: float | None = None
_REFRESHING: bool = False
_LAST_ERROR: str | None = None


def _placeholder(now_ts: float, last_error: str | None) -> dict[str, Any]:
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now_ts))
    return {
        "indicators": [
            {"indicator": "VIX", "value": None, "error": last_error or "warming up", "name": "标普500波动率指数"},
            {"indicator": "OVX", "value": None, "error": last_error or "warming up", "name": "原油ETF波动率指数"},
            {"indicator": "GVZ", "value": None, "error": last_error or "warming up", "name": "黄金ETF波动率指数"},
            {"indicator": "US10Y", "value": None, "error": last_error or "warming up", "name": "美国10年期国债收益率"},
        ],
        "ashare_sentiment": None,
        "composite": {
            "composite_fear_greed_index": 50,
            "overall_sentiment": "中性",
            "action_suggestion": "按策略正常操作",
            "score_details": [],
            "contagion_analysis": None,
            "timestamp": ts_str,
        },
        "refreshing": True,
        "cache_ts": _CACHE_TS,
        "lastError": last_error,
    }


def _refresh() -> None:
    global _CACHE, _CACHE_TS, _REFRESHING, _LAST_ERROR
    try:
        from .nanobot_macro import compute_fear_snapshot

        data = compute_fear_snapshot(include_ashare=False)
        with _LOCK:
            _CACHE = data
            _CACHE_TS = time.time()
            _LAST_ERROR = None
    except Exception as e:
        with _LOCK:
            _LAST_ERROR = f"{type(e).__name__}: {e}"
    finally:
        with _LOCK:
            _REFRESHING = False


def _trigger_refresh() -> None:
    global _REFRESHING
    with _LOCK:
        if _REFRESHING:
            return
        _REFRESHING = True
    threading.Thread(target=_refresh, daemon=True).start()


def get_macro_latest() -> dict[str, Any]:
    if str(os.getenv("CHARLES_SENTIMENT_TEST_MODE") or "").strip() == "1":
        return {
            "indicators": [
                {"indicator": "VIX", "value": 18.6, "date": "2026-05-02", "name": "标普500波动率指数"},
                {"indicator": "OVX", "value": 32.4, "date": "2026-05-02", "name": "原油ETF波动率指数"},
                {"indicator": "GVZ", "value": 14.2, "date": "2026-05-02", "name": "黄金ETF波动率指数"},
                {"indicator": "US10Y", "value": 4.28, "date": "2026-05-02", "name": "美国10年期国债收益率"},
            ],
            "ashare_sentiment": None,
            "composite": {
                "composite_fear_greed_index": 58,
                "overall_sentiment": "中性",
                "action_suggestion": "按策略正常操作",
                "score_details": [],
                "contagion_analysis": None,
                "timestamp": "2026-05-02 15:10:00",
            },
        }

    global _CACHE, _CACHE_TS, _LAST_ERROR, _REFRESHING
    now = time.time()
    with _LOCK:
        data = _CACHE
        ts = _CACHE_TS
        refreshing = _REFRESHING
        last_error = _LAST_ERROR

    if data is not None and ts is not None and (now - ts) < 600:
        out = dict(data)
        out["refreshing"] = refreshing
        out["cache_ts"] = ts
        out["lastError"] = last_error
        return out

    if data is not None:
        if not refreshing:
            _trigger_refresh()
        out = dict(data)
        out["refreshing"] = True
        out["cache_ts"] = ts
        out["lastError"] = last_error
        return out

    _trigger_refresh()
    return _placeholder(now, last_error)
