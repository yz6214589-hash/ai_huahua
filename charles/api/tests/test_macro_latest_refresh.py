import time

import pytest


def test_macro_returns_stale_cache_and_triggers_refresh(monkeypatch: pytest.MonkeyPatch):
    import charles_api.sentiment.macro as m

    m._CACHE = {
        "indicators": [],
        "composite": {"composite_fear_greed_index": 1, "overall_sentiment": "x", "action_suggestion": "y", "timestamp": "t"},
    }
    m._CACHE_TS = time.time() - 700
    m._REFRESHING = False
    m._LAST_ERROR = "E"

    started = {"v": False}

    class DummyThread:
        def __init__(self, target, daemon):
            self._target = target
            self._daemon = daemon

        def start(self):
            started["v"] = True

    monkeypatch.setattr(m.threading, "Thread", lambda target, daemon: DummyThread(target, daemon))

    out = m.get_macro_latest()
    assert out["refreshing"] is True
    assert started["v"] is True


def test_macro_returns_placeholder_when_no_cache(monkeypatch: pytest.MonkeyPatch):
    import charles_api.sentiment.macro as m

    m._CACHE = None
    m._CACHE_TS = None
    m._REFRESHING = False
    m._LAST_ERROR = None

    class DummyThread:
        def __init__(self, target, daemon):
            return None

        def start(self):
            return None

    monkeypatch.setattr(m.threading, "Thread", lambda target, daemon: DummyThread(target, daemon))

    out = m.get_macro_latest()
    assert out["refreshing"] is True
    assert isinstance(out.get("indicators"), list)
    assert len(out["indicators"]) == 4

