from __future__ import annotations

from fastapi import Body, FastAPI
from fastapi.testclient import TestClient

from zoe.app.mainforce.params import validate_mainforce_params


def _client():
    app = FastAPI()

    @app.post("/tasks")
    def create(payload: dict = Body(...)):
        params = validate_mainforce_params(payload.get("params") or {})
        return {"params": params}

    return TestClient(app)


def test_mainforce_api_like_validation_rejects_invalid_params():
    client = _client()
    r = client.post("/tasks", json={"params": {"n_ticks": 10}})
    assert r.status_code == 400
    assert r.json().get("detail", {}).get("error") == "invalid_params"


def test_mainforce_api_like_validation_rejects_unknown_keys():
    client = _client()
    r = client.post("/tasks", json={"params": {"foo": 1}})
    assert r.status_code == 400
    assert r.json().get("detail", {}).get("error") == "invalid_params"
