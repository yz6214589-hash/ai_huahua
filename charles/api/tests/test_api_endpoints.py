import os
from datetime import date, datetime
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client2(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> TestClient:
    os.environ["CHARLES_SKIP_APP_IMPORT"] = "1"
    os.environ["CHARLES_JOB_STORE_DIR"] = str(tmp_path / "job_runs")

    import importlib

    mod = importlib.import_module("charles_api.app")

    store: dict[str, Any] = {
        "master": {"600000.SH": "浦发银行", "000001.SZ": "平安银行"},
        "watchlist": [{"stock_code": "600000.SH", "pinned": 0, "sort_order": 1}],
        "schedule": {},
        "daily": {
            "600000.SH": [
                {
                    "trade_date": date(2026, 4, 1),
                    "open_price": 9.9,
                    "high_price": 10.2,
                    "low_price": 9.8,
                    "close_price": 10.0,
                    "volume": 1000,
                    "amount": 10000.0,
                    "ma5": 9.9,
                    "ma10": 9.8,
                    "ma20": 9.7,
                    "ma60": 9.5,
                    "vol_ma5": 900,
                    "vol_ma20": 800,
                    "rsi14": 51.123,
                    "macd_dif": 0.11,
                    "macd_dea": 0.09,
                    "macd_hist": 0.02,
                    "boll_upper": 10.5,
                    "boll_mid": 10.0,
                    "boll_lower": 9.5,
                    "kdj_k": 50.1,
                    "kdj_d": 48.9,
                    "kdj_j": 52.3,
                    "stock_name": "浦发银行",
                }
            ]
        },
        "financial": {
            "600000.SH": [
                {
                    "report_date": date(2025, 12, 31),
                    "revenue": 100.0,
                    "net_profit": 10.0,
                    "eps": 1.0,
                    "roe": 12.34,
                    "operating_cashflow": 5.0,
                    "total_assets": 1000.0,
                    "total_equity": 200.0,
                },
                {
                    "report_date": date(2024, 12, 31),
                    "revenue": 90.0,
                    "net_profit": 9.0,
                    "eps": 0.9,
                    "roe": 11.0,
                    "operating_cashflow": 4.0,
                    "total_assets": 900.0,
                    "total_equity": 180.0,
                },
            ]
        },
        "news": {
            "600000.SH": [
                {
                    "title": "新闻A",
                    "source": "eastmoney",
                    "source_url": "https://example.com/a",
                    "published_at": datetime(2026, 4, 2, 10, 0, 0),
                }
            ]
        },
        "reports": {
            "600000.SH": [
                {
                    "broker": "券商A",
                    "report_date": date(2026, 4, 1),
                    "rating": "买入",
                    "target_price": 12.34,
                    "source_file": None,
                }
            ]
        },
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

        if "select count(*) as c from trade_stock_master" in s:
            return [{"c": len(store["master"])}]

        if "from trade_stock_master where stock_code in" in s:
            codes = list(p)
            out = []
            for c in codes:
                out.append({"code": c, "name": store["master"].get(c)})
            return out

        if "from trade_stock_master where stock_code like" in s or "from trade_stock_master where stock_name like" in s:
            like = str(p[0]).strip("%")
            out = []
            for code, name in store["master"].items():
                if like in code or (name and like in name):
                    out.append({"code": code, "name": name})
            return out

        if "from trade_stock_master order by stock_code" in s:
            out = [{"code": c, "name": n} for c, n in sorted(store["master"].items())]
            return out[: int(p[0])]

        if "select count(*) as c from trade_watchlist" in s:
            return [{"c": len(store["watchlist"])}]

        if "from trade_watchlist w left join trade_stock_master" in s:
            out = []
            for x in sorted(store["watchlist"], key=lambda r: (-int(r["pinned"]), int(r["sort_order"]))):
                out.append({"stock_code": x["stock_code"], "pinned": x["pinned"], "sort_order": x["sort_order"], "stock_name": store["master"].get(x["stock_code"])})
            return out

        if "select stock_name, trade_date, close_price from trade_stock_daily" in s:
            code = p[0]
            rows = store["daily"].get(code) or []
            if not rows:
                return []
            r0 = rows[0]
            return [{"stock_name": r0.get("stock_name"), "trade_date": r0["trade_date"], "close_price": r0["close_price"]}]

        if "from trade_stock_financial" in s and "order by report_date desc" in s:
            code = p[0]
            rows = store["financial"].get(code) or []
            out = []
            for r in rows[:2]:
                out.append({k: r.get(k) for k in ("report_date", "revenue", "net_profit", "eps", "roe", "operating_cashflow", "total_assets", "total_equity")})
            return out

        if "from trade_stock_daily" in s and "order by trade_date desc limit 1" in s:
            code = p[0]
            rows = store["daily"].get(code) or []
            if not rows:
                return []
            r0 = rows[0]
            return [{k: r0.get(k) for k in ("trade_date", "ma5", "ma10", "ma20", "ma60", "vol_ma5", "vol_ma20", "rsi14", "macd_dif", "macd_dea", "macd_hist", "boll_upper", "boll_mid", "boll_lower", "kdj_k", "kdj_d", "kdj_j")}]

        if "from trade_stock_daily" in s and "order by trade_date asc" in s:
            code = p[0]
            rows = store["daily"].get(code) or []
            out = []
            for r in rows:
                row = {k: r.get(k) for k in ("trade_date", "open_price", "high_price", "low_price", "close_price", "volume", "amount", "ma5", "ma10", "ma20", "ma60", "vol_ma5", "vol_ma20", "rsi14", "macd_dif", "macd_dea", "macd_hist", "boll_upper", "boll_mid", "boll_lower", "kdj_k", "kdj_d", "kdj_j")}
                out.append(row)
            return out

        if "select count(*) as c from trade_stock_news" in s:
            code = p[0]
            return [{"c": len(store["news"].get(code) or [])}]

        if "from trade_stock_news" in s and "order by published_at desc" in s:
            code = p[0]
            out = []
            for r in (store["news"].get(code) or [])[: int(p[1])]:
                out.append({"title": r["title"], "source": r["source"], "source_url": r["source_url"], "published_at": r["published_at"]})
            return out

        if "select count(*) as c from trade_report_consensus" in s:
            code = p[0]
            return [{"c": len(store["reports"].get(code) or [])}]

        if "from trade_report_consensus" in s and "order by report_date desc" in s:
            code = p[0]
            out = []
            for r in (store["reports"].get(code) or [])[: int(p[1])]:
                out.append({k: r.get(k) for k in ("broker", "report_date", "rating", "target_price", "source_file")})
            return out

        if s.startswith("select count(*) as c from trade_stock_daily"):
            return [{"c": 1}]

        if s.startswith("select") and "from trade_stock_daily" in s and "limit" in s and "offset" in s:
            r0 = store["daily"]["600000.SH"][0]
            return [{"stock_code": "600000.SH", "trade_date": r0["trade_date"], "open_price": r0["open_price"], "high_price": r0["high_price"], "low_price": r0["low_price"], "close_price": r0["close_price"], "volume": r0["volume"], "amount": r0["amount"]}]

        if "select max(trade_date) as d, count(*) as c from trade_stock_daily" in s:
            return [{"d": date(2026, 4, 1), "c": 1}]
        if "select max(report_date) as d, count(*) as c from trade_stock_financial" in s:
            return [{"d": date(2025, 12, 31), "c": 2}]
        if "select max(published_at) as d, count(*) as c from trade_stock_news" in s:
            return [{"d": datetime(2026, 4, 2, 10, 0, 0), "c": 1}]
        if "select max(indicator_date) as d, count(*) as c from trade_macro_indicator" in s:
            return [{"d": None, "c": 0}]
        if "select max(rate_date) as d, count(*) as c from trade_rate_daily" in s:
            return [{"d": None, "c": 0}]
        if "select max(report_date) as d, count(*) as c from trade_report_consensus" in s:
            return [{"d": date(2026, 4, 1), "c": 1}]
        if "select max(event_date) as d, count(*) as c from trade_calendar_event" in s:
            return [{"d": None, "c": 0}]

        if "select domain from trade_job_schedule" in s:
            return [{"domain": k} for k in store["schedule"].keys()]

        if "select domain, enabled, cron, timezone, mode, params_json from trade_job_schedule" in s:
            out = []
            for k, v in store["schedule"].items():
                out.append({"domain": k, "enabled": v["enabled"], "cron": v["cron"], "timezone": v["timezone"], "mode": v.get("mode"), "params_json": v.get("params_json") or "{}"})
            return out

        if "select domain, enabled, cron, timezone, mode, params_json, updated_at from trade_job_schedule" in s:
            out = []
            for k, v in store["schedule"].items():
                out.append({"domain": k, "enabled": v["enabled"], "cron": v["cron"], "timezone": v["timezone"], "mode": v.get("mode"), "params_json": v.get("params_json") or "{}", "updated_at": None})
            return out

        return []

    def execute(_conn: DummyConn, sql: str, params: tuple[Any, ...] | None = None) -> int:
        p = params or ()
        s = " ".join(sql.split()).lower()
        if s.startswith("insert into trade_watchlist"):
            store["watchlist"].append({"stock_code": p[0], "pinned": 0, "sort_order": int(p[1])})
            return 1
        if s.startswith("delete from trade_watchlist"):
            store["watchlist"] = [x for x in store["watchlist"] if x["stock_code"] != p[0]]
            return 1
        if s.startswith("update trade_watchlist set pinned"):
            for x in store["watchlist"]:
                if x["stock_code"] == p[1]:
                    x["pinned"] = int(p[0])
            return 1
        if "insert into trade_job_schedule" in s:
            store["schedule"][p[0]] = {"enabled": int(p[1]), "cron": p[2], "timezone": p[3], "mode": p[4], "params_json": p[5]}
            return 1
        return 0

    def executemany(_conn: DummyConn, sql: str, rows: list[tuple[Any, ...]]) -> int:
        s = " ".join(sql.split()).lower()
        if s.startswith("insert into trade_job_schedule"):
            for domain, enabled, cron, tz, mode, params_json in rows:
                store["schedule"][domain] = {"enabled": int(enabled), "cron": cron, "timezone": tz, "mode": mode, "params_json": params_json}
            return len(rows)
        if s.startswith("update trade_watchlist set sort_order"):
            for sort_order, code in rows:
                for x in store["watchlist"]:
                    if x["stock_code"] == code:
                        x["sort_order"] = int(sort_order)
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
            return pd.DataFrame([{"BPS": 5.0, "EPSJB": 1.0, "ROEJQ": 12.34, "REPORT_DATE": date(2025, 12, 31)}])

    monkeypatch.setitem(__import__("sys").modules, "akshare", DummyAk)

    app = mod.create_app()
    return TestClient(app)


def test_stocks_search(client2: TestClient):
    r = client2.get("/api/stocks?q=浦发&limit=10")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(x["code"] == "600000.SH" for x in items)


def test_snapshot_and_fundamentals(client2: TestClient):
    s = client2.get("/api/stock/600000.SH/snapshot").json()
    assert s["stock_code"] == "600000.SH"
    f = client2.get("/api/stock/600000.SH/fundamentals").json()
    assert f["stock_code"] == "600000.SH"
    assert any(x["key"] == "pe" for x in f["items"])


def test_technical_series_and_feed(client2: TestClient):
    r = client2.get("/api/stock/600000.SH/technical/series?start=2026-03-01&end=2026-04-30")
    assert r.status_code == 200
    assert len(r.json()["rows"]) >= 1

    n = client2.get("/api/stock/600000.SH/feed?tab=news&page=1&pageSize=5")
    assert n.status_code == 200
    assert n.json()["total"] == 1

    rep = client2.get("/api/stock/600000.SH/feed?tab=reports&page=1&pageSize=5")
    assert rep.status_code == 200
    assert rep.json()["total"] == 1


def test_summary_and_data(client2: TestClient):
    s = client2.get("/api/summary")
    assert s.status_code == 200

    d = client2.get("/api/data/trade_stock_daily?page=1&pageSize=1&stock_code=600000.SH&trade_date=2026-04-01,2026-04-01")
    assert d.status_code == 200

