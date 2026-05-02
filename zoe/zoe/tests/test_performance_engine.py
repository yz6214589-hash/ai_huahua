from __future__ import annotations

import numpy as np
import pandas as pd


def test_compute_chart_series_basic():
    from zoe.app.performance.charts import compute_chart_series

    idx = pd.date_range("2025-01-01", periods=6, freq="D")
    returns = pd.Series([0.01, -0.02, 0.0, 0.03, -0.01, 0.02], index=idx)

    series = compute_chart_series(returns)

    assert series["dates"] == [d.date().isoformat() for d in idx]
    assert len(series["nav"]) == len(idx)
    assert len(series["cum_return"]) == len(idx)
    assert len(series["drawdown"]) == len(idx)
    assert len(series["rolling_sharpe"]) == len(idx)
    assert "heatmap" in series


def test_svd_market_state_thresholds():
    from zoe.app.performance.svd import diagnose_market_regime

    idx = pd.date_range("2025-01-01", periods=160, freq="B")

    base = np.random.default_rng(1).normal(0, 0.01, size=len(idx))
    df_sync = pd.DataFrame({f"s{i}": base for i in range(6)}, index=idx)
    res_sync = diagnose_market_regime(df_sync, window=120, step=20)
    assert res_sync["current_state"] == "齐涨齐跌"

    rng = np.random.default_rng(2)
    df_div = pd.DataFrame({f"s{i}": rng.normal(0, 0.01, size=len(idx)) for i in range(8)}, index=idx)
    res_div = diagnose_market_regime(df_div, window=120, step=20)
    assert res_div["current_state"] in ("板块分化", "个股行情")


def test_calc_quantstats_metrics_contains_keys():
    from zoe.app.performance.quantstats_engine import calc_quantstats_metrics

    idx = pd.date_range("2025-01-01", periods=40, freq="B")
    returns = pd.Series(np.random.default_rng(3).normal(0, 0.01, size=len(idx)), index=idx)

    metrics = calc_quantstats_metrics(returns)
    assert "total_return" in metrics
    assert "cagr" in metrics
    assert "max_drawdown" in metrics
    assert "sharpe" in metrics


def test_generate_report_html_writes_file(tmp_path, monkeypatch):
    from zoe.app.performance.report import generate_report_html

    def fake_html(*_, **kwargs):
        out = kwargs.get("output")
        with open(out, "w", encoding="utf-8") as f:
            f.write("<html><body>ok</body></html>")

    import quantstats as qs

    monkeypatch.setattr(qs.reports, "html", fake_html)

    idx = pd.date_range("2025-01-01", periods=10, freq="B")
    returns = pd.Series(np.random.default_rng(4).normal(0, 0.01, size=len(idx)), index=idx)

    res = generate_report_html(returns=returns, benchmark=None, output_dir=str(tmp_path), title="t")
    assert res["report_path"].endswith(".html")
    assert (tmp_path / res["report_filename"]).exists()


def test_read_nav_csv_bytes():
    from zoe.app.performance.io import read_nav_csv_bytes

    b = "date,nav\n2025-01-01,1.0\n2025-01-02,1.1\n".encode("utf-8")
    s = read_nav_csv_bytes(b)
    assert list(s.index.date.astype(str)) == ["2025-01-01", "2025-01-02"]
    assert list(s.values) == [1.0, 1.1]


def test_parse_broker_csv_bytes_minimal():
    from zoe.app.performance.broker import load_broker_csv_bytes_list

    csv = (
        "证券代码,证券名称,成交日期,买卖方向,成交数量,成交价格,成交金额,佣金,印花税,过户费\n"
        "600519,贵州茅台,2025-01-02,买入,100,10,1000,1,0,0\n"
        "600519,贵州茅台,2025-01-03,卖出,100,11,1100,1,1,0\n"
    ).encode("utf-8")
    df = load_broker_csv_bytes_list([csv])
    assert len(df) == 2
    assert "标准代码" in df.columns
    assert df["标准代码"].iloc[0] == "600519.SH"
