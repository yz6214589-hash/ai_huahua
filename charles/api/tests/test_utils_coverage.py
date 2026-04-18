import json
import os
from datetime import datetime, timezone

import pandas as pd

from charles_api.cleaning.ohlcv import _safe_float, _safe_int, clean_ohlcv_frame
from charles_api.db import executemany, execute, query_dict
from charles_api.job_store import init_running, list_runs, read_run, write_run
from charles_api.models import JobDomain


class _Cursor:
    def __init__(self, rows):
        self._rows = rows
        self.rowcount = len(rows)
        self._executed = False

    def execute(self, _sql, _params):
        self._executed = True
        return None

    def executemany(self, _sql, _rows):
        self._executed = True
        self.rowcount = len(list(_rows))
        return None

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, _t, _v, _tb):
        return False


class _Conn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, *_args, **_kwargs):
        return _Cursor(self._rows)


def test_safe_number_helpers():
    assert _safe_float("1.2") == 1.2
    assert _safe_float("x") is None
    assert _safe_float(float("nan")) is None
    assert _safe_int("100") == 100
    assert _safe_int("x") is None


def test_clean_ohlcv_frame_filters_invalid():
    df = pd.DataFrame(
        {
            "open": [1, 2],
            "high": [1, 3],
            "low": [2, 0],
            "close": [1, 2],
            "volume": [10, 20],
        },
        index=["20260101", "20260102"],
    )
    out = clean_ohlcv_frame(df)
    assert len(out) == 1
    assert out.index[0] == "20260102"


def test_db_helpers():
    conn = _Conn([{"ok": 1}])
    assert query_dict(conn, "SELECT 1") == [{"ok": 1}]
    assert execute(conn, "UPDATE t SET a=1") == 1
    assert executemany(conn, "INSERT INTO t VALUES (%s)", [(1,), (2,)]) == 2
    assert executemany(conn, "INSERT INTO t VALUES (%s)", []) == 0


def test_job_store_roundtrip(tmp_path):
    store_dir = str(tmp_path / "runs")
    run = init_running(JobDomain.stock_daily)
    write_run(store_dir, run)
    obj = read_run(store_dir, run.runId)
    assert obj is not None
    assert obj["runId"] == run.runId

    r2 = init_running(JobDomain.stock_news)
    r2 = r2.model_copy(update={"startedAt": datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat()})
    write_run(store_dir, r2)
    r1 = run.model_copy(update={"startedAt": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()})
    write_run(store_dir, r1)

    out = list_runs(store_dir, None, 10)
    assert [x["runId"] for x in out][:2] == [r2.runId, r1.runId]

    out_news = list_runs(store_dir, JobDomain.stock_news, 10)
    assert all(x["domain"] == "stock_news" for x in out_news)
