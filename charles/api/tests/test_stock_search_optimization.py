import os
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_stock_search_master(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> TestClient:
    os.environ["CHARLES_SKIP_APP_IMPORT"] = "1"
    os.environ["CHARLES_JOB_STORE_DIR"] = str(tmp_path / "job_runs")

    import importlib

    mod = importlib.import_module("charles_api.app")

    store = {
        "master": [
            {"code": "600000.SH", "name": "浦发银行"},
            {"code": "000001.SZ", "name": "平安银行"},
        ]
    }

    class DummyConn:
        def commit(self) -> None:
            return None

        def close(self) -> None:
            return None

    def connect(_cfg: Any) -> DummyConn:
        return DummyConn()

    def query_dict(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        s = " ".join(sql.split()).lower()
        if "from trade_stock_master" in s and "select stock_code as code" in s:
            return store["master"]
        if "from trade_stock_daily" in s:
            raise AssertionError("should not query trade_stock_daily for chinese name search")
        return []

    def execute(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> int:
        return 0

    def executemany(_conn: DummyConn, sql: str, rows: Any) -> int:
        return 0

    monkeypatch.setattr(mod, "connect", connect)
    monkeypatch.setattr(mod, "query_dict", query_dict)
    monkeypatch.setattr(mod, "execute", execute)
    monkeypatch.setattr(mod, "executemany", executemany)

    app = mod.create_app()
    return TestClient(app)


@pytest.fixture()
def client_stock_search_no_master(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> TestClient:
    os.environ["CHARLES_SKIP_APP_IMPORT"] = "1"
    os.environ["CHARLES_JOB_STORE_DIR"] = str(tmp_path / "job_runs")

    import importlib

    mod = importlib.import_module("charles_api.app")

    class DummyConn:
        def commit(self) -> None:
            return None

        def close(self) -> None:
            return None

    def connect(_cfg: Any) -> DummyConn:
        return DummyConn()

    def query_dict(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        s = " ".join(sql.split()).lower()
        if "from trade_stock_master" in s and "select stock_code as code" in s:
            return []
        if "from trade_stock_daily" in s:
            raise AssertionError("should not query trade_stock_daily for chinese name search when no master")
        return []

    def execute(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> int:
        return 0

    def executemany(_conn: DummyConn, sql: str, rows: Any) -> int:
        return 0

    monkeypatch.setattr(mod, "connect", connect)
    monkeypatch.setattr(mod, "query_dict", query_dict)
    monkeypatch.setattr(mod, "execute", execute)
    monkeypatch.setattr(mod, "executemany", executemany)

    app = mod.create_app()
    return TestClient(app)


def test_stocks_chinese_search_uses_master_cache(client_stock_search_master: TestClient):
    r = client_stock_search_master.get("/api/stocks?q=%E6%B5%A6%E5%8F%91&limit=10")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any("浦发" in (x.get("name") or "") for x in items)


def test_stocks_chinese_search_degrades_without_master(client_stock_search_no_master: TestClient):
    r = client_stock_search_no_master.get("/api/stocks?q=%E6%B5%A6%E5%8F%91&limit=10")
    assert r.status_code == 200
    assert r.json()["items"] == []

