from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class Decision(Enum):
    APPROVE = "approve"
    WARN = "warn"
    REJECT = "reject"
    HALT = "halt"


@dataclass
class RiskDecision:
    decision: Decision
    reason: str
    rule_name: str
    max_position_pct: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def is_approved(self) -> bool:
        return self.decision in (Decision.APPROVE, Decision.WARN)

    @property
    def is_rejected(self) -> bool:
        return self.decision in (Decision.REJECT, Decision.HALT)


@dataclass
class Order:
    stock_code: str
    direction: str
    amount: float
    price: float
    quantity: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def __post_init__(self):
        if self.quantity == 0 and self.price > 0:
            self.quantity = int(self.amount / self.price / 100) * 100


class PreTradeGuard:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.max_order_amount = float(cfg.get("max_order_amount", 200_000))
        self.price_collar_pct = float(cfg.get("price_collar_pct", 0.05))
        self.blacklist = set(cfg.get("blacklist", []))
        self.atr_risk_pct = float(cfg.get("atr_risk_pct", 0.01))
        self.atr_overshoot_ratio = float(cfg.get("atr_overshoot_ratio", 2.0))

    def check_all(self, order: Order, portfolio: dict) -> List[RiskDecision]:
        results = [
            self.check_order_amount(order),
            self.check_price_collar(order, portfolio),
            self.check_blacklist(order),
        ]
        atr_result = self.check_atr_position(order, portfolio)
        if atr_result:
            results.append(atr_result)
        return results

    def check_order_amount(self, order: Order) -> RiskDecision:
        if order.amount > self.max_order_amount:
            return RiskDecision(
                decision=Decision.REJECT,
                reason=f"单笔金额 {order.amount:,.0f} 超过上限 {self.max_order_amount:,.0f}",
                rule_name="单笔金额上限",
            )
        return RiskDecision(
            decision=Decision.APPROVE,
            reason=f"单笔金额 {order.amount:,.0f} 在限额内",
            rule_name="单笔金额上限",
        )

    def check_price_collar(self, order: Order, portfolio: dict) -> RiskDecision:
        prices = portfolio.get("prices", {})
        current_price = float(prices.get(order.stock_code, 0) or 0)
        if current_price <= 0:
            return RiskDecision(
                decision=Decision.APPROVE,
                reason="无现价信息, 跳过价格偏离检查",
                rule_name="价格偏离检查",
            )

        deviation = abs(order.price - current_price) / current_price
        if deviation > self.price_collar_pct:
            return RiskDecision(
                decision=Decision.REJECT,
                reason=f"委托价 {order.price:.3f} 偏离现价 {current_price:.3f} 达 {deviation:.1%}, 超过 {self.price_collar_pct:.0%} 限制",
                rule_name="价格偏离检查",
            )
        return RiskDecision(
            decision=Decision.APPROVE,
            reason=f"价格偏离 {deviation:.2%}, 正常",
            rule_name="价格偏离检查",
        )

    def check_blacklist(self, order: Order) -> RiskDecision:
        is_st = "_ST" in order.stock_code.upper() or "ST" in order.stock_code.upper()
        if is_st or order.stock_code in self.blacklist:
            return RiskDecision(
                decision=Decision.REJECT,
                reason=f"{order.stock_code} 命中 ST/黑名单, 禁止买入",
                rule_name="ST黑名单",
            )
        return RiskDecision(
            decision=Decision.APPROVE,
            reason=f"{order.stock_code} 不在黑名单",
            rule_name="ST黑名单",
        )

    def check_atr_position(self, order: Order, portfolio: dict) -> Optional[RiskDecision]:
        atr_data = portfolio.get("atr", {})
        atr_value = float(atr_data.get(order.stock_code, 0) or 0)
        if atr_value <= 0 or order.direction != "buy":
            return None

        total_asset = float(portfolio.get("total_asset", 0) or 0)
        if total_asset <= 0:
            return None

        suggested_position = (total_asset * self.atr_risk_pct) / atr_value * order.price
        atr_stop_price = order.price - 2 * atr_value

        if order.amount > suggested_position * self.atr_overshoot_ratio:
            return RiskDecision(
                decision=Decision.WARN,
                reason=(
                    f"ATR={atr_value:.3f}, 建议仓位 {suggested_position:,.0f}元, "
                    f"实际 {order.amount:,.0f}元 (超 {order.amount/suggested_position:.1f}倍). "
                    f"ATR止损价: {atr_stop_price:.3f}"
                ),
                rule_name="ATR仓位检查",
                max_position_pct=suggested_position / order.amount,
            )
        return RiskDecision(
            decision=Decision.APPROVE,
            reason=(
                f"ATR={atr_value:.3f}, 建议仓位 {suggested_position:,.0f}元, "
                f"实际 {order.amount:,.0f}元, 风险可控. ATR止损参考: {atr_stop_price:.3f}"
            ),
            rule_name="ATR仓位检查",
        )


class CircuitBreaker:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.max_daily_loss_pct = float(cfg.get("max_daily_loss_pct", 0.02))
        self.atr_stop_multiplier = float(cfg.get("atr_stop_multiplier", 2.0))
        self.daily_start_nav = 0.0
        self.current_nav = 0.0
        self.is_halted = False
        self.halt_reason = ""
        self.atr_stops: Dict[str, dict] = {}

    def reset_daily(self, start_nav: float):
        self.daily_start_nav = float(start_nav or 0)
        self.current_nav = float(start_nav or 0)
        self.is_halted = False
        self.halt_reason = ""

    def update_nav(self, nav: float) -> Optional[RiskDecision]:
        self.current_nav = float(nav or 0)
        if self.daily_start_nav <= 0:
            return None
        loss_pct = (self.daily_start_nav - self.current_nav) / self.daily_start_nav
        if loss_pct >= self.max_daily_loss_pct:
            self.is_halted = True
            self.halt_reason = f"单日亏损 {loss_pct:.2%} 触发熔断线 {self.max_daily_loss_pct:.2%}"
            return RiskDecision(decision=Decision.HALT, reason=self.halt_reason, rule_name="单日亏损熔断")
        return None

    def register_position(self, stock_code: str, entry_price: float, atr: float):
        if atr <= 0:
            return
        self.atr_stops[stock_code] = {
            "entry_price": float(entry_price),
            "atr": float(atr),
            "stop_price": float(entry_price) - self.atr_stop_multiplier * float(atr),
        }

    def remove_position(self, stock_code: str):
        self.atr_stops.pop(stock_code, None)

    def check_atr_stop(self, stock_code: str, current_price: float) -> Optional[RiskDecision]:
        info = self.atr_stops.get(stock_code)
        if not info:
            return None
        if float(current_price) <= float(info["stop_price"]):
            return RiskDecision(
                decision=Decision.REJECT,
                reason=(
                    f"{stock_code} 触发ATR止损: 入场价 {info['entry_price']:.3f}, "
                    f"ATR={info['atr']:.3f}, 止损价 {info['stop_price']:.3f}, "
                    f"现价 {float(current_price):.3f}"
                ),
                rule_name="ATR止损",
            )
        return None

    def get_status(self) -> dict:
        daily_pnl_pct = (self.current_nav - self.daily_start_nav) / self.daily_start_nav if self.daily_start_nav > 0 else 0
        return {
            "daily_start_nav": self.daily_start_nav,
            "current_nav": self.current_nav,
            "daily_pnl_pct": daily_pnl_pct,
            "is_halted": self.is_halted,
            "halt_reason": self.halt_reason,
            "atr_stops": dict(self.atr_stops),
        }


class EventKeywordChecker:
    BEARISH_KEYWORDS = [
        "退市",
        "暂停上市",
        "终止上市",
        "*ST",
        "立案调查",
        "立案侦查",
        "行政处罚",
        "涉嫌违法",
        "涉嫌犯罪",
        "财务造假",
    ]

    def __init__(self, keywords: List[str] | None = None):
        self.keywords = keywords or list(self.BEARISH_KEYWORDS)

    def check(self, stock_code: str, news_text: str) -> RiskDecision:
        if not news_text:
            return RiskDecision(decision=Decision.APPROVE, reason=f"{stock_code} 无近期新闻, 跳过", rule_name="事件关键词")
        for kw in self.keywords:
            if kw in news_text:
                return RiskDecision(decision=Decision.REJECT, reason=f"{stock_code} 新闻命中重大利空: {kw}", rule_name="事件关键词")
        return RiskDecision(decision=Decision.APPROVE, reason=f"{stock_code} 新闻未发现重大利空", rule_name="事件关键词")


class MacroGate:
    def __init__(self):
        self.current_vix: float | None = None
        self.position_coefficient: float = 1.0
        self.risk_level: str = "未知"

    def update_vix(self, vix: float) -> float:
        self.current_vix = float(vix)
        if self.current_vix >= 50:
            self.position_coefficient = 0.0
            self.risk_level = "末日级别"
        elif self.current_vix >= 35:
            self.position_coefficient = 0.30 - (self.current_vix - 35) / 15 * 0.20
            self.risk_level = "极度恐慌"
        elif self.current_vix >= 25:
            self.position_coefficient = 0.70 - (self.current_vix - 25) / 10 * 0.40
            self.risk_level = "恐慌"
        elif self.current_vix >= 20:
            self.position_coefficient = 1.00 - (self.current_vix - 20) / 5 * 0.30
            self.risk_level = "焦虑"
        else:
            self.position_coefficient = 1.0
            self.risk_level = "正常"
        return self.position_coefficient

    def check(self) -> RiskDecision:
        if self.current_vix is None:
            return RiskDecision(decision=Decision.APPROVE, reason="未提供 VIX, 跳过宏观门控", rule_name="宏观VIX门控")
        if self.position_coefficient <= 0:
            return RiskDecision(
                decision=Decision.HALT,
                reason=f"VIX={self.current_vix:.1f} 极度恐慌, 暂停所有开仓",
                rule_name="宏观VIX门控",
                max_position_pct=0.0,
            )
        if self.position_coefficient < 1.0:
            return RiskDecision(
                decision=Decision.WARN,
                reason=f"VIX={self.current_vix:.1f} ({self.risk_level}), 仓位系数降至 {self.position_coefficient:.0%}",
                rule_name="宏观VIX门控",
                max_position_pct=self.position_coefficient,
            )
        return RiskDecision(decision=Decision.APPROVE, reason=f"VIX={self.current_vix:.1f} 正常, 仓位系数 100%", rule_name="宏观VIX门控")


class RiskManager:
    def __init__(self, config: dict | None = None, event_checker=None):
        cfg = config or {}
        self.pre_trade = PreTradeGuard(cfg.get("pre_trade", {}))
        self.circuit_breaker = CircuitBreaker(cfg.get("circuit_breaker", {}))
        self.event = event_checker or EventKeywordChecker(cfg.get("event_keywords"))
        self.macro = MacroGate()
        self.audit_log: List[dict] = []

    def approve_verbose(self, order: Order, portfolio: dict, context: dict | None = None) -> tuple[RiskDecision, List[RiskDecision]]:
        context = context or {}
        checks: List[RiskDecision] = []

        if self.circuit_breaker.is_halted:
            d = RiskDecision(Decision.HALT, f"交易已熔断: {self.circuit_breaker.halt_reason}", rule_name="熔断状态")
            checks.append(d)
            self._log(order, d)
            return d, checks

        macro_d = self.macro.check()
        checks.append(macro_d)
        if macro_d.decision == Decision.HALT:
            self._log(order, macro_d)
            return macro_d, checks

        if order.direction == "buy":
            news_text = context.get("news_text", "")
            event_d = self.event.check(order.stock_code, news_text)
            checks.append(event_d)
            if event_d.decision == Decision.REJECT:
                final = self._get_strictest(checks)
                self._log(order, final)
                return final, checks

        checks.extend(self.pre_trade.check_all(order, portfolio))

        final = self._get_strictest(checks)
        self._log(order, final)
        return final, checks

    def approve(self, order: Order, portfolio: dict, context: dict | None = None) -> RiskDecision:
        final, _ = self.approve_verbose(order, portfolio, context)
        return final

    def on_trade_complete(self, nav: float) -> Optional[RiskDecision]:
        return self.circuit_breaker.update_nav(nav)

    def register_position(self, stock_code: str, entry_price: float, atr: float):
        self.circuit_breaker.register_position(stock_code, entry_price, atr)

    def remove_position(self, stock_code: str):
        self.circuit_breaker.remove_position(stock_code)

    def check_atr_stop(self, stock_code: str, current_price: float) -> Optional[RiskDecision]:
        return self.circuit_breaker.check_atr_stop(stock_code, current_price)

    def start_day(self, start_nav: float):
        self.circuit_breaker.reset_daily(start_nav)

    def _get_strictest(self, decisions: List[RiskDecision]) -> RiskDecision:
        severity = {Decision.HALT: 4, Decision.REJECT: 3, Decision.WARN: 2, Decision.APPROVE: 1}
        decisions_sorted = sorted(decisions, key=lambda d: severity.get(d.decision, 0), reverse=True)
        strictest = decisions_sorted[0]

        rejections = [d for d in decisions if d.is_rejected]
        warnings = [d for d in decisions if d.decision == Decision.WARN]

        if rejections:
            reasons = "; ".join(f"[{d.rule_name}] {d.reason}" for d in rejections)
            return RiskDecision(decision=strictest.decision, reason=reasons, rule_name="综合审批")
        if warnings:
            min_pct = min(d.max_position_pct for d in warnings)
            reasons = "; ".join(f"[{d.rule_name}] {d.reason}" for d in warnings)
            return RiskDecision(decision=Decision.WARN, reason=reasons, rule_name="综合审批", max_position_pct=min_pct)
        return RiskDecision(decision=Decision.APPROVE, reason="所有检查通过", rule_name="综合审批")

    def _log(self, order: Order, decision: RiskDecision):
        self.audit_log.append(
            {
                "time": decision.timestamp,
                "stock": order.stock_code,
                "direction": order.direction,
                "amount": order.amount,
                "decision": decision.decision.value,
                "rule": decision.rule_name,
                "reason": decision.reason,
            }
        )

    def get_summary(self) -> dict:
        total = len(self.audit_log)
        approved = sum(1 for e in self.audit_log if e["decision"] == "approve")
        warned = sum(1 for e in self.audit_log if e["decision"] == "warn")
        rejected = sum(1 for e in self.audit_log if e["decision"] in ("reject", "halt"))
        return {
            "total": total,
            "approved": approved,
            "warned": warned,
            "rejected": rejected,
            "rejection_rate": rejected / total if total > 0 else 0,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "macro": {
                "vix": self.macro.current_vix,
                "coefficient": self.macro.position_coefficient,
                "risk_level": self.macro.risk_level,
            },
        }
