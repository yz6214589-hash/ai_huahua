"""
MiniQMT 交易者封装模块

封装 XtQuant Python SDK 提供的交易接口，提供面向对象的交易操作能力。
支持连接管理、账户订阅、买卖下单、撤单及实时事件回调等功能。
"""

from __future__ import annotations

import datetime
import time
from typing import Any


class MiniQMTTrader:
    """
    MiniQMT 交易者类

    封装与 MiniQMT 终端的交互逻辑，提供：
    - 连接与断开管理
    - 账户资产查询
    - 持仓查询
    - 订单查询
    - 成交查询
    - 买卖下单
    - 撤单操作
    - 实时事件回调处理
    """

    def __init__(
        self,
        qmt_path: str,
        account_id: str,
        session_id: int | None = None,
        max_positions: int = 10,
        max_order_amount: float = 500000,
    ) -> None:
        """
        初始化 MiniQMT 交易者

        Args:
            qmt_path: MiniQMT 终端安装路径
            account_id: 交易账户 ID
            session_id: 会话 ID（可选，默认使用当前时间戳）
            max_positions: 最大持仓数量限制
            max_order_amount: 单笔订单最大金额限制
        """
        self.qmt_path = qmt_path
        self.account_id = account_id
        # 如果未指定 session_id，则使用当前时间戳作为会话标识
        self.session_id = session_id or int(time.time())
        self.max_positions = max_positions
        self.max_order_amount = max_order_amount

        # 内部状态变量
        self._trader: Any = None
        self._account: Any = None
        self._connected = False
        self._events: list[dict[str, Any]] = []

        # 缓存 XtQuant SDK 的类和常量（延迟导入）
        self._xtconstant: Any = None
        self._XtQuantTrader: Any = None
        self._XtQuantTraderCallback: Any = None
        self._StockAccount: Any = None

    def _now(self) -> str:
        """获取当前时间字符串（时:分:秒格式）"""
        return datetime.datetime.now().strftime("%H:%M:%S")

    @property
    def connected(self) -> bool:
        """返回当前连接状态"""
        return self._connected

    @property
    def events(self) -> list[dict[str, Any]]:
        """返回事件日志列表的副本"""
        return list(self._events)

    def _append_event(self, typ: str, message: str, data: dict[str, Any] | None = None) -> None:
        """
        添加事件到事件日志

        Args:
            typ: 事件类型
            message: 事件消息描述
            data: 事件携带的附加数据（可选）
        """
        self._events.append(
            {
                "ts": self._now(),
                "type": typ,
                "message": message,
                "data": data or {},
            }
        )

    def _ensure_imports(self) -> None:
        """
        确保 XtQuant SDK 相关类已正确导入

        使用延迟导入策略，仅在首次需要时加载 SDK 模块
        """
        if self._XtQuantTrader is not None:
            return
        # 导入 XtQuant SDK 的核心类
        from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
        from xtquant.xttype import StockAccount
        from xtquant import xtconstant

        # 缓存导入的类供后续使用
        self._XtQuantTrader = XtQuantTrader
        self._XtQuantTraderCallback = XtQuantTraderCallback
        self._StockAccount = StockAccount
        self._xtconstant = xtconstant

    def connect(self, max_retry: int = 3) -> bool:
        """
        连接到 MiniQMT 终端

        创建交易者实例，注册回调处理器，尝试建立连接。
        支持自动重试机制，增强连接的稳定性。

        Args:
            max_retry: 最大重试次数，默认 3 次

        Returns:
            连接是否成功

        Raises:
            RuntimeError: 连接或订阅失败时抛出
        """
        self._ensure_imports()

        owner = self
        XtQuantTraderCallback = self._XtQuantTraderCallback

        class _Cb(XtQuantTraderCallback):
            """交易事件回调处理器"""

            def on_disconnected(self) -> None:
                """连接断开回调"""
                owner._append_event("disconnected", "连接断开")

            def on_account_status(self, status: Any) -> None:
                """账户状态变更回调"""
                owner._append_event(
                    "account_status",
                    "账户状态更新",
                    {"account_id": getattr(status, "account_id", None), "status": getattr(status, "status", None)},
                )

            def on_stock_order(self, order: Any) -> None:
                """委托订单推送回调"""
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
                """成交回报回调"""
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
                """委托失败回调"""
                owner._append_event(
                    "order_error",
                    "委托失败",
                    {"order_id": getattr(order_error, "order_id", None), "error_msg": getattr(order_error, "error_msg", None)},
                )

            def on_cancel_error(self, cancel_error: Any) -> None:
                """撤单失败回调"""
                owner._append_event(
                    "cancel_error",
                    "撤单失败",
                    {"order_id": getattr(cancel_error, "order_id", None), "error_msg": getattr(cancel_error, "error_msg", None)},
                )

            def on_order_stock_async_response(self, response: Any) -> None:
                """异步下单响应回调"""
                owner._append_event(
                    "async_response",
                    "异步响应",
                    {"order_id": getattr(response, "order_id", None), "seq": getattr(response, "seq", None)},
                )

        # 创建交易者实例并注册回调
        self._trader = self._XtQuantTrader(self.qmt_path, self.session_id)
        self._trader.register_callback(_Cb())
        self._trader.start()

        # 尝试建立连接（支持重试）
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

        # 订阅账户信息
        self._account = self._StockAccount(self.account_id)
        sub_result = self._trader.subscribe(self._account)
        if sub_result != 0:
            raise RuntimeError(f"订阅账户失败: {sub_result}")

        self._connected = True
        self._append_event("connected", "连接成功", {"account_id": self.account_id})
        return True

    def disconnect(self) -> None:
        """
        断开与 MiniQMT 终端的连接

        停止交易者并更新连接状态
        """
        if self._trader is None:
            return
        try:
            self._trader.stop()
        finally:
            self._connected = False
            self._append_event("disconnected", "已断开连接")

    def query_asset(self) -> dict[str, Any]:
        """
        查询账户资产信息

        Returns:
            包含总资产、现金、市值、冻结资金的字典
        """
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
        """
        查询当前持仓信息

        过滤掉持仓数量为0的记录，只返回有实际持仓的数据。

        Returns:
            持仓信息列表，每项包含股票代码、数量、可用量等
        """
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
        """
        查询当日订单记录

        Returns:
            订单列表，包含订单号、股票代码、委托数量、成交数量等
        """
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
        """
        查询当日成交记录

        Returns:
            成交列表，包含成交ID、股票代码、成交价格、成交量等
        """
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
        """
        风险检查

        检查下单是否符合风控规则，包括：
        - 持仓数量限制
        - 单笔订单金额限制

        Args:
            stock_code: 股票代码
            volume: 委托数量
            price: 委托价格

        Returns:
            是否通过风控检查
        """
        positions = self._trader.query_stock_positions(self._account) or []
        held = [p for p in positions if (getattr(p, "volume", 0) or 0) > 0]
        if held:
            held_codes = {getattr(p, "stock_code", None) for p in held}
            # 检查是否超过最大持仓数量
            if len(held_codes) >= self.max_positions and stock_code not in held_codes:
                return False
        # 检查单笔订单金额
        if price > 0:
            if float(volume) * float(price) > float(self.max_order_amount):
                return False
        return True

    def buy(self, stock_code: str, volume: int, price: float = 0.0, strategy_name: str = "", remark: str = "") -> int | None:
        """
        买入股票

        根据参数提交买入订单。如果价格大于0则使用限价单，
        否则使用市价单（根据股票交易所选择对应的市价单类型）。
        下单前会进行风险检查。

        Args:
            stock_code: 股票代码（如 "600000.SH"）
            volume: 买入数量（必须为100的整数倍）
            price: 买入价格（0表示市价单）
            strategy_name: 策略名称（可选）
            remark: 备注信息（可选）

        Returns:
            订单ID，失败时返回 None
        """
        if not self._connected:
            return None
        xtconstant = self._xtconstant
        # 根据是否有指定价格选择订单类型
        if price > 0:
            price_type = xtconstant.FIX_PRICE  # 限价单
        else:
            # 根据交易所选择市价单类型
            price_type = xtconstant.MARKET_SH_CONVERT_5_LIMIT if stock_code.endswith(".SH") else xtconstant.MARKET_SZ_CONVERT_5_CANCEL

        # 风控检查
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
        """
        卖出股票

        根据参数提交卖出订单。如果价格大于0则使用限价单，
        否则使用市价单。卖出前会进行风险检查。

        Args:
            stock_code: 股票代码（如 "600000.SH"）
            volume: 卖出数量
            price: 卖出价格（0表示市价单）
            strategy_name: 策略名称（可选）
            remark: 备注信息（可选）

        Returns:
            订单ID，失败时返回 None
        """
        if not self._connected:
            return None
        xtconstant = self._xtconstant
        # 根据是否有指定价格选择订单类型
        if price > 0:
            price_type = xtconstant.FIX_PRICE  # 限价单
        else:
            # 根据交易所选择市价单类型
            price_type = xtconstant.MARKET_SH_CONVERT_5_LIMIT if stock_code.endswith(".SH") else xtconstant.MARKET_SZ_CONVERT_5_CANCEL

        # 风控检查
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

    # ─────────── 历史行情（xtdata） ───────────

    def download_history_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
    ) -> bool:
        """
        下载指定股票的历史行情数据到本地缓存。

        Args:
            stock_code: 股票代码，如 "600519.SH"
            period: K 线周期，"1m"/"5m"/"15m"/"30m"/"60m"/"1d"/"1w"/"1M"
            start_time: 开始时间，YYYYMMDD 或 YYYYMMDDHHmmss
            end_time: 结束时间，默认为空表示至今

        Returns:
            是否下载成功
        """
        try:
            from xtquant import xtdata
            xtdata.download_history_data(
                stock_code=stock_code,
                period=period,
                start_time=start_time,
                end_time=end_time,
            )
            return True
        except Exception:
            return False

    def get_market_data(
        self,
        stock_list: list[str],
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: str = "none",
        fill_data: bool = True,
    ) -> dict[str, Any]:
        """
        获取股票历史行情数据（OHLCV）。

        Args:
            stock_list: 股票代码列表
            period: K 线周期，默认 "1d"
            start_time: 开始时间，YYYYMMDD 或 YYYYMMDDHHmmss
            end_time: 结束时间
            count: 数量，-1 表示全部
            dividend_type: 复权类型，"none"/"front"/"back"，默认不复权
            fill_data: 是否填充空值

        Returns:
            包含 date/close/open/high/low/volume 等字段的 dict
        """
        try:
            from xtquant import xtdata
            return xtdata.get_market_data(
                stock_list=stock_list,
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=count,
                dividend_type=dividend_type,
                fill_data=fill_data,
            )
        except Exception:
            return {}

    # ─────────── 交易接口 ───────────

    def cancel(self, order_id: int) -> int | None:
        """
        撤销指定订单

        根据订单ID撤销未完全成交的委托。

        Args:
            order_id: 要撤销的订单ID

        Returns:
            订单ID，失败时返回 None
        """
        if not self._connected:
            return None
        return int(self._trader.cancel_order_stock(self._account, int(order_id)))

