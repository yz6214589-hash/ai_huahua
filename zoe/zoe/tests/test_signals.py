from __future__ import annotations

import pandas as pd

from zoe.app.signals import generate_signals


def test_generate_signals_cross_and_boll():
    df = pd.DataFrame(
        [
            {
                "trade_date": "2025-01-01",
                "close": 10.0,
                "ma20": 10.0,
                "boll_lower": 9.0,
                "boll_upper": 11.0,
                "boll_mid": 10.0,
                "macd_hist": -0.1,
                "rsi14": 45.0,
            },
            {
                "trade_date": "2025-01-02",
                "close": 11.0,
                "ma20": 10.0,
                "boll_lower": 12.0,
                "boll_upper": 14.0,
                "boll_mid": 13.0,
                "macd_hist": 0.2,
                "rsi14": 48.0,
            },
            {
                "trade_date": "2025-01-03",
                "close": 9.0,
                "ma20": 10.0,
                "boll_lower": 8.0,
                "boll_upper": 12.0,
                "boll_mid": 10.0,
                "macd_hist": -0.2,
                "rsi14": 72.0,
            },
        ]
    )

    sigs = generate_signals(df)
    assert any(s.signal == "BUY" and s.trade_date == "2025-01-02" for s in sigs)
    assert any(s.signal == "SELL" and s.trade_date == "2025-01-03" for s in sigs)

