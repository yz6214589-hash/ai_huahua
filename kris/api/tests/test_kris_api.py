import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestKirsApi(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from kris_api.app import create_app

        self.client = TestClient(create_app())

    def test_approve_reject_max_order_amount(self):
        self.client.post("/api/kris/start-day", json={"start_nav": 1_000_000})
        self.client.post("/api/kris/update-macro", json={"vix": 18.0})

        resp = self.client.post(
            "/api/kris/approve",
            json={
                "order": {"stock_code": "510050.SH", "direction": "buy", "amount": 500_000, "price": 3.0},
                "portfolio": {
                    "total_asset": 1_000_000,
                    "prices": {"510050.SH": 3.0},
                    "atr": {"510050.SH": 0.05},
                },
                "context": {"news_text": ""},
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["decision"], "reject")
        self.assertIn("单笔金额", data["reason"])

    def test_approve_warn_returns_suggestions(self):
        self.client.post("/api/kris/start-day", json={"start_nav": 1_000_000})
        self.client.post("/api/kris/update-macro", json={"vix": 18.0})

        resp = self.client.post(
            "/api/kris/approve",
            json={
                "order": {"stock_code": "510050.SH", "direction": "buy", "amount": 200_000, "price": 3.0},
                "portfolio": {
                    "total_asset": 100_000,
                    "prices": {"510050.SH": 3.0},
                    "atr": {"510050.SH": 0.05},
                },
                "context": {"news_text": ""},
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["decision"], "warn")
        self.assertEqual(data["suggested_amount"], 60_000)
        self.assertEqual(data["suggested_quantity"], 20_000)

    def test_macro_halt_vix_50(self):
        self.client.post("/api/kris/start-day", json={"start_nav": 1_000_000})
        self.client.post("/api/kris/update-macro", json={"vix": 50.0})

        resp = self.client.post(
            "/api/kris/approve",
            json={
                "order": {"stock_code": "510050.SH", "direction": "buy", "amount": 100_000, "price": 3.0},
                "portfolio": {
                    "total_asset": 1_000_000,
                    "prices": {"510050.SH": 3.0},
                    "atr": {"510050.SH": 0.05},
                },
                "context": {"news_text": "卖出单也走审批，但不走事件关键词"},
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["decision"], "halt")

    def test_macro_halt_allows_sell(self):
        self.client.post("/api/kris/start-day", json={"start_nav": 1_000_000})
        self.client.post("/api/kris/update-macro", json={"vix": 50.0})

        resp = self.client.post(
            "/api/kris/approve",
            json={
                "order": {"stock_code": "510050.SH", "direction": "sell", "amount": 100_000, "price": 3.0},
                "portfolio": {
                    "total_asset": 1_000_000,
                    "prices": {"510050.SH": 3.0},
                    "atr": {"510050.SH": 0.05},
                },
                "context": {"news_text": "立案调查 财务造假"},
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["decision"], "approve")
