import os
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    os.environ["CHARLES_SKIP_APP_IMPORT"] = "1"

    import importlib

    mod = importlib.import_module("charles_api.app")

    store: dict[str, Any] = {
        "watchlist": [],
        "master": {"600000.SH": "浦发银行", "000001.SZ": "平安银行"},
        "daily_latest": {"600000.SH": {"stock_name": "浦发银行", "close_price": 10.0}, "000001.SZ": {"stock_name": "平安银行", "close_price": 12.0}},
        "schedule": {},
    }

    class DummyConn:
        def commit(self) -> None:
            return None

        def close(self) -> None:
            return None

    def connect(_cfg: Any) -> DummyConn:
        return DummyConn()

    def query_dict(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        p = params or ()
        s = " ".join(sql.split()).lower()

        if "select count(*) as c from trade_watchlist" in s:
            return [{"c": len(store["watchlist"])}]
        if "select 1 as ok from trade_watchlist where stock_code" in s:
            code = p[0]
            return [{"ok": 1}] if any(x["stock_code"] == code for x in store["watchlist"]) else []
        if "select coalesce(max(sort_order),0) as m from trade_watchlist" in s:
            m = max([x["sort_order"] for x in store["watchlist"]] or [0])
            return [{"m": m}]
        if "from trade_watchlist w left join trade_stock_master" in s:
            out = []
            for x in sorted(store["watchlist"], key=lambda r: (-int(r["pinned"]), int(r["sort_order"]))):
                out.append(
                    {
                        "stock_code": x["stock_code"],
                        "pinned": x["pinned"],
                        "sort_order": x["sort_order"],
                        "stock_name": store["master"].get(x["stock_code"]),
                    }
                )
            return out
        if "select stock_name from trade_stock_master where stock_code" in s:
            code = p[0]
            name = store["master"].get(code)
            return [{"stock_name": name}] if name else []
        if "select stock_name, trade_date, close_price from trade_stock_daily where stock_code" in s:
            code = p[0]
            row = store["daily_latest"].get(code)
            if not row:
                return []
            return [{"stock_name": row["stock_name"], "trade_date": "2026-04-02", "close_price": row["close_price"]}]
        if "select domain from trade_job_schedule" in s:
            return [{"domain": k} for k in store["schedule"].keys()]
        if "select domain, enabled, cron, timezone, mode, params_json, updated_at from trade_job_schedule" in s:
            out = []
            for k, v in sorted(store["schedule"].items()):
                out.append(
                    {
                        "domain": k,
                        "enabled": v["enabled"],
                        "cron": v["cron"],
                        "timezone": v["timezone"],
                        "mode": v.get("mode"),
                        "params_json": v.get("params_json") or "{}",
                        "updated_at": None,
                    }
                )
            return out
        if "select domain, enabled, cron, timezone, mode, params_json from trade_job_schedule" in s:
            out = []
            for k, v in sorted(store["schedule"].items()):
                out.append({"domain": k, "enabled": v["enabled"], "cron": v["cron"], "timezone": v["timezone"], "mode": v.get("mode"), "params_json": v.get("params_json") or "{}"})
            return out

        return []

    def execute(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> int:
        p = params or ()
        s = " ".join(sql.split()).lower()

        if s.startswith("insert into trade_watchlist"):
            code = p[0]
            sort_order = int(p[1])
            store["watchlist"].append({"stock_code": code, "pinned": 0, "sort_order": sort_order})
            return 1
        if s.startswith("delete from trade_watchlist"):
            code = p[0]
            before = len(store["watchlist"])
            store["watchlist"] = [x for x in store["watchlist"] if x["stock_code"] != code]
            return before - len(store["watchlist"])
        if s.startswith("update trade_watchlist set pinned"):
            pinned = int(p[0])
            code = p[1]
            for x in store["watchlist"]:
                if x["stock_code"] == code:
                    x["pinned"] = pinned
            return 1
        if "insert into trade_job_schedule" in s:
            domain = p[0]
            store["schedule"][domain] = {"enabled": int(p[1]), "cron": p[2], "timezone": p[3], "mode": p[4], "params_json": p[5]}
            return 1

        return 0

    def executemany(_conn: DummyConn, sql: str, rows: list[tuple[Any, ...]]) -> int:
        s = " ".join(sql.split()).lower()
        if s.startswith("update trade_watchlist set sort_order"):
            for sort_order, code in rows:
                for x in store["watchlist"]:
                    if x["stock_code"] == code:
                        x["sort_order"] = int(sort_order)
            return len(rows)
        if s.startswith("insert into trade_job_schedule"):
            for domain, enabled, cron, tz, mode, params_json in rows:
                store["schedule"][domain] = {"enabled": int(enabled), "cron": cron, "timezone": tz, "mode": mode, "params_json": params_json}
            return len(rows)
        return 0

    monkeypatch.setattr(mod, "connect", connect)
    monkeypatch.setattr(mod, "query_dict", query_dict)
    monkeypatch.setattr(mod, "execute", execute)
    monkeypatch.setattr(mod, "executemany", executemany)

    class DummyAk:
        @staticmethod
        def stock_zh_a_spot_em():
            return pd.DataFrame([])

        @staticmethod
        def stock_financial_analysis_indicator_em(symbol: str, indicator: str = "按报告期"):
            return pd.DataFrame([])

    monkeypatch.setitem(__import__("sys").modules, "akshare", DummyAk)

    app = mod.create_app()
    return TestClient(app)


def test_watchlist_add_and_list(client: TestClient):
    r = client.post("/api/watchlist", json={"stock_code": "600000.SH"})
    assert r.status_code == 200
    r2 = client.get("/api/watchlist")
    assert r2.status_code == 200
    data = r2.json()
    assert data["items"][0]["stock_code"] == "600000.SH"


def test_watchlist_pin_and_delete(client: TestClient):
    client.post("/api/watchlist", json={"stock_code": "000001.SZ"})
    r = client.put("/api/watchlist/000001.SZ/pin", json={"pinned": True})
    assert r.status_code == 200
    data = client.get("/api/watchlist").json()
    assert data["items"][0]["pinned"] is True
    r2 = client.delete("/api/watchlist/000001.SZ")
    assert r2.status_code == 200
    assert client.get("/api/watchlist").json()["items"] == []


def test_watchlist_reorder(client: TestClient):
    client.post("/api/watchlist", json={"stock_code": "600000.SH"})
    client.post("/api/watchlist", json={"stock_code": "000001.SZ"})
    client.put("/api/watchlist/reorder", json={"codes": ["000001.SZ", "600000.SH"]})
    items = client.get("/api/watchlist").json()["items"]
    assert [x["stock_code"] for x in items] == ["000001.SZ", "600000.SH"]

