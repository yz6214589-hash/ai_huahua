from modules.analysis.tech_signals import generate_signals


def test_generate_signals_trend_buy_cross_ma20() -> None:
    trade_dates = [f"2024-01-{i:02d}" for i in range(1, 22)]
    closes = [100.0] * 20 + [110.0]
    signals = generate_signals(trade_dates=trade_dates, closes=closes)
    assert signals
    day = [x for x in signals if x.get("trade_date") == "2024-01-21"]
    assert day
    assert any(x.get("signal") == "BUY" for x in day)
    buy = next(x for x in day if x.get("signal") == "BUY")
    assert any("价格上穿MA20" in x for x in (buy.get("reasons") or []))
