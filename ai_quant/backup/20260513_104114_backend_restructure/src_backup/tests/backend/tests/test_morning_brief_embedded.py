from __future__ import annotations

from pathlib import Path


def test_ceo_integration_has_no_external_dependency() -> None:
    p = Path(__file__).resolve().parents[1] / "" / "modules" / "console" / "service.py"
    text = p.read_text(encoding="utf-8")
    assert "sys.path.insert" not in text
    assert "from ceo." not in text
    assert "services.ceo" not in text


def test_morning_brief_graph_produces_report() -> None:
    from workflow.morning_brief_graph import build_graph

    graph = build_graph()
    result = graph.invoke(
        {
            "trigger_time": None,
            "industry_level": 2,
            "top_n_industries": 2,
            "top_n_stocks": 2,
            "lookback_days": 30,
            "sample_stocks": 10,
            "messages": [],
            "industry_rank": [
                {
                    "industry": "电子",
                    "rank": 1,
                    "score": 1.2,
                    "raw_score": 0.8,
                    "MOM_21": 3.1,
                    "RS_60": 1.8,
                    "VOL_R": 1.1,
                    "phase": "neutral",
                    "phase_desc": "中性",
                    "ROC_20": 2.0,
                    "members": 100,
                }
            ],
            "picked_stocks": [{"code": "000001.SZ", "industry": "电子", "alpha": 0.12, "raw_factors": {"MOM_3M": 0.05}}],
        }
    )
    assert "report_md" in result
    assert "report_html" in result
    assert isinstance(result.get("picked_stocks"), list)
    assert str(result.get("report_md") or "").startswith("# ")
    assert "<html" in str(result.get("report_html") or "")
