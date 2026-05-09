from __future__ import annotations

import io
import json
import urllib.request

from fastapi.testclient import TestClient

from ai_quant_api.app import create_app


class _Resp:
    def __init__(self, payload: dict):
        self._b = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self) -> bytes:
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_trading_state_proxy(monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_QMT_GATEWAY_BASE", "http://qmt-gw:9001")

    def fake_urlopen(req: urllib.request.Request, timeout: int = 0):
        assert req.full_url == "http://qmt-gw:9001/api/trading/state"
        return _Resp({"connected": False, "account_id": "test", "session_id": 1, "events_count": 0, "last_event": None})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = TestClient(create_app())
    resp = client.get("/api/trading/state")
    assert resp.status_code == 200
    body = resp.json()
    assert body["account_id"] == "test"

