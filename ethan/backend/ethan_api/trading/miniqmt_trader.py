from __future__ import annotations

import datetime
import time
from typing import Any


class MiniQMTTrader:
    def __init__(
        self,
        qmt_path: str,
        account_id: str,
        session_id: int | None = None,
        max_positions: int = 10,
        max_order_amount: float = 500000,
    ) -> None:
        self.qmt_path = qmt_path
        self.account_id = account_id
        self.session_id = session_id or int(time.time())
        self.max_positions = max_positions
        self.max_order_amount = max_order_amount

        self._trader: Any = None
        self._account: Any = None
        self._connected = False
        self._events: list[dict[str, Any]] = []

        self._xtconstant: Any = None
        self._XtQuantTrader: Any = None
        self._XtQuantTraderCallback: Any = None
        self._StockAccount: Any = None

    def _now(self) -> str:
        return datetime.datetime.now().strftime("%H:%M:%S")

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def _append_event(self, typ: str, message: str, data: dict[str, Any] | None = None) -> None:
        self._events.append(
            {
                "ts": self._now(),
                "type": typ,
                "message": message,
                "data": data or {},
            }
        )

    def _ensure_imports(self) -> None:
        if self._XtQuantTrader is not None:
            return
        from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
        from xtquant.xttype import StockAccount
        from xtquant import xtconstant

        self._XtQuantTrader = XtQuantTrader
        self._XtQuantTraderCallback = XtQuantTraderCallback
        self._StockAccount = StockAccount
        self._xtconstant = xtconstant

    def connect(self, max_retry: int = 3) -> bool:
        self._ensure_imports()

        owner = self
        XtQuantTraderCallback = self._XtQuantTraderCallback

        class _Cb(XtQuantTraderCallback):
            def on_disconnected(self) -> None:
                owner._append_event("disconnected", "连接断开")

            def on_account_status(self, status: Any) -> None:
                owner._append_event(
                    "account_status",
                    "账户状态更新",
                    {"account_id": getattr(status, "account_id", None), "status": getattr(status, "status", None)},
                )

            def on_stock_order(self, order: Any) -> None:
                owner._append_event(
                    "order",
                    "委托推送",
                    {
                        "stock_code": getattr(order, "stock_code", None),
                        "order_id": getattr(order, "order_id", None),
                        "order_volume": getattr(order, "order_volume", None),
                        "traded_volume": getattr(order, "traded_volume", None),
                        "order_status": getattr(order, "order_status", None),
                        "order_type": getattr(order, "order_type", None),
                        "price": getattr(order, "price", None),
                    },
                )

            def on_stock_trade(self, trade: Any) -> None:
                owner._append_event(
                    "trade",
                    "成交回报",
                    {
                        "stock_code": getattr(trade, "stock_code", None),
                        "order_id": getattr(trade, "order_id", None),
                        "traded_volume": getattr(trade, "traded_volume", None),
                        "traded_price": getattr(trade, "traded_price", None),
                        "traded_amount": getattr(trade, "traded_amount", None),
                        "traded_time": getattr(trade, "traded_time", None),
                    },
                )

            def on_order_error(self, order_error: Any) -> None:
                owner._append_event(
                    "order_error",
                    "委托失败",
                    {"order_id": getattr(order_error, "order_id", None), "error_msg": getattr(order_error, "error_msg", None)},
                )

            def on_cancel_error(self, cancel_error: Any) -> None:
                owner._append_event(
                    "cancel_error",
                    "撤单失败",
                    {"order_id": getattr(cancel_error, "order_id", None), "error_msg": getattr(cancel_error, "error_msg", None)},
                )

            def on_order_stock_async_response(self, response: Any) -> None:
                owner._append_event(
                    "async_response",
                    "异步响应",
                    {"order_id": getattr(response, "order_id", None), "seq": getattr(response, "seq", None)},
                )

        self._trader = self._XtQuantTrader(self.qmt_path, self.session_id)
        self._trader.register_callback(_Cb())
        self._trader.start()

        ok = False
        last_error: str | None = None
        for _ in range(max_retry):
            try:
                result = self._trader.connect()
                if result == 0:
                    ok = True
                    break
                last_error = f"connect_result={result}"
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
            time.sleep(1.5)

        if not ok:
            raise RuntimeError(f"连接 MiniQMT 失败: {last_error or 'unknown'}")

        self._account = self._StockAccount(self.account_id)
        sub_result = self._trader.subscribe(self._account)
        if sub_result != 0:
            raise RuntimeError(f"订阅账户失败: {sub_result}")

        self._connected = True
        self._append_event("connected", "连接成功", {"account_id": self.account_id})
        return True

    def disconnect(self) -> None:
        if self._trader is None:
            return
        try:
            self._trader.stop()
        finally:
            self._connected = False
            self._append_event("disconnected", "已断开连接")

    def query_asset(self) -> dict[str, Any]:
        if not self._connected:
            return {}
        asset = self._trader.query_stock_asset(self._account)
        if asset is None:
            return {}
        return {
            "total_asset": getattr(asset, "total_asset", None),
            "cash": getattr(asset, "cash", None),
            "market_value": getattr(asset, "market_value", None),
            "frozen_cash": getattr(asset, "frozen_cash", None),
        }

    def query_positions(self) -> list[dict[str, Any]]:
        if not self._connected:
            return []
        positions = self._trader.query_stock_positions(self._account) or []
        out: list[dict[str, Any]] = []
        for p in positions:
            vol = getattr(p, "volume", 0) or 0
            if vol <= 0:
                continue
            out.append(
                {
                    "stock_code": getattr(p, "stock_code", None),
                    "volume": vol,
                    "can_use_volume": getattr(p, "can_use_volume", None),
                    "open_price": getattr(p, "open_price", None),
                    "market_value": getattr(p, "market_value", None),
                }
            )
        return out

    def query_orders(self) -> list[dict[str, Any]]:
        if not self._connected:
            return []
        orders = self._trader.query_stock_orders(self._account) or []
        return [
            {
                "order_id": getattr(o, "order_id", None),
                "stock_code": getattr(o, "stock_code", None),
                "order_type": getattr(o, "order_type", None),
                "order_volume": getattr(o, "order_volume", None),
                "price": getattr(o, "price", None),
                "traded_volume": getattr(o, "traded_volume", None),
                "order_status": getattr(o, "order_status", None),
                "order_time": getattr(o, "order_time", None),
            }
            for o in orders
        ]

    def query_trades(self) -> list[dict[str, Any]]:
        if not self._connected:
            return []
        trades = self._trader.query_stock_trades(self._account) or []
        return [
            {
                "traded_id": getattr(t, "traded_id", None),
                "stock_code": getattr(t, "stock_code", None),
                "traded_price": getattr(t, "traded_price", None),
                "traded_volume": getattr(t, "traded_volume", None),
                "traded_amount": getattr(t, "traded_amount", None),
                "order_id": getattr(t, "order_id", None),
                "traded_time": getattr(t, "traded_time", None),
            }
            for t in trades
        ]

    def _check_risk(self, stock_code: str, volume: int, price: float) -> bool:
        positions = self._trader.query_stock_positions(self._account) or []
        held = [p for p in positions if (getattr(p, "volume", 0) or 0) > 0]
        if held:
            held_codes = {getattr(p, "stock_code", None) for p in held}
            if len(held_codes) >= self.max_positions and stock_code not in held_codes:
                return False
        if price > 0:
            if float(volume) * float(price) > float(self.max_order_amount):
                return False
        return True

    def buy(self, stock_code: str, volume: int, price: float = 0.0, strategy_name: str = "", remark: str = "") -> int | None:
        if not self._connected:
            return None
        xtconstant = self._xtconstant
        if price > 0:
            price_type = xtconstant.FIX_PRICE
        else:
            price_type = xtconstant.MARKET_SH_CONVERT_5_LIMIT if stock_code.endswith(".SH") else xtconstant.MARKET_SZ_CONVERT_5_CANCEL
        if not self._check_risk(stock_code, volume, price):
            return None
        return int(
            self._trader.order_stock(
                self._account,
                stock_code,
                xtconstant.STOCK_BUY,
                int(volume),
                price_type,
                float(price) if price > 0 else 0.0,
                strategy_name,
                remark,
            )
        )

    def sell(self, stock_code: str, volume: int, price: float = 0.0, strategy_name: str = "", remark: str = "") -> int | None:
        if not self._connected:
            return None
        xtconstant = self._xtconstant
        if price > 0:
            price_type = xtconstant.FIX_PRICE
        else:
            price_type = xtconstant.MARKET_SH_CONVERT_5_LIMIT if stock_code.endswith(".SH") else xtconstant.MARKET_SZ_CONVERT_5_CANCEL
        if not self._check_risk(stock_code, volume, price):
            return None
        return int(
            self._trader.order_stock(
                self._account,
                stock_code,
                xtconstant.STOCK_SELL,
                int(volume),
                price_type,
                float(price) if price > 0 else 0.0,
                strategy_name,
                remark,
            )
        )

    def cancel(self, order_id: int) -> int | None:
        if not self._connected:
            return None
        return int(self._trader.cancel_order_stock(self._account, int(order_id)))

