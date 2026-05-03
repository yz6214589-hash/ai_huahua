from __future__ import annotations


def test_health_has_deps_info():
    from zoe.app.main import health

    h = health()
    assert isinstance(h, dict)
    assert "deps" in h
    deps = h["deps"]
    assert isinstance(deps, dict)
    for k in ["websockets", "quantstats", "yfinance"]:
        assert k in deps
        item = deps[k]
        assert isinstance(item, dict)
        assert item.get("package") in ["websockets", "quantstats", "yfinance"]

