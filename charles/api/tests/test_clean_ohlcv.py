import unittest

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from charles_api.cleaning.ohlcv import clean_ohlcv_frame


class TestCleanOhlcvFrame(unittest.TestCase):
    def test_drops_non_numeric_rows(self):
        df = pd.DataFrame(
            {
                "open": [10, "bad"],
                "high": [11, 12],
                "low": [9, 10],
                "close": [10.5, 11],
                "volume": [100, 200],
                "amount": [1000, 2000],
            },
            index=["20240102", "20240103"],
        )

        out = clean_ohlcv_frame(df)
        self.assertEqual(list(out.index), ["20240102"])
        self.assertEqual(float(out.loc["20240102", "open"]), 10.0)

    def test_drops_inconsistent_high_low(self):
        df = pd.DataFrame(
            {
                "open": [10],
                "high": [9],
                "low": [8],
                "close": [8.5],
                "volume": [100],
            },
            index=["20240102"],
        )
        out = clean_ohlcv_frame(df)
        self.assertEqual(len(out), 0)


if __name__ == "__main__":
    unittest.main()

