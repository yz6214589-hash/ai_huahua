"""
风控模块 - 风险管理与订单审批
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

_RISK_MANAGER = None


def _get_manager():
    global _RISK_MANAGER
    if _RISK_MANAGER is not None:
        return _RISK_MANAGER
    _RISK_MANAGER = RiskManager()
    return _RISK_MANAGER


class Decision(Enum):
    APPROVE = "APPROVE"
    WARN = "WARN"
    REJECT = "REJECT"


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    reason: str
    rule_name: str
    max_position_pct: float
    timestamp: str


@dataclass(frozen=True)
class Order:
    stock_code: str
    direction: str
    amount: float
    price: float
    quantity: int


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class RiskManager:
    def __init__(self) -> None:
        self.audit_log: list[dict[str, Any]] = []

    def get_summary(self) -> dict[str, Any]:
        return {"source": "risk", "status": "ready", "features": ["approve", "audit"], "mode": "embedded"}

    def approve_verbose(self, order: Order, portfolio: dict[str, Any], context: dict[str, Any]):
        ts = _now_iso()
        checks: list[DecisionResult] = []

        total_asset = float(portfolio.get("total_asset") or 0.0)
        if total_asset <= 0.0:
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="invalid_total_asset",
                rule_name="portfolio.total_asset",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks

        direction = str(order.direction or "").lower().strip()
        if direction not in ("buy", "sell"):
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="invalid_direction",
                rule_name="order.direction",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks

        amount = float(order.amount or 0.0)
        if amount <= 0.0:
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="invalid_amount",
                rule_name="order.amount",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks

        max_pct = 0.1
        prices = portfolio.get("prices") if isinstance(portfolio.get("prices"), dict) else {}
        atrs = portfolio.get("atr") if isinstance(portfolio.get("atr"), dict) else {}
        px = prices.get(order.stock_code)
        atr = atrs.get(order.stock_code)
        try:
            px_f = float(px) if px is not None else float(order.price or 0.0)
        except Exception:
            px_f = float(order.price or 0.0)
        try:
            atr_f = float(atr) if atr is not None else None
        except Exception:
            atr_f = None

        if atr_f is not None and px_f > 0:
            vol = atr_f / px_f
            if vol >= 0.06:
                max_pct = min(max_pct, 0.05)
                checks.append(
                    DecisionResult(
                        decision=Decision.WARN,
                        reason="high_volatility",
                        rule_name="portfolio.atr",
                        max_position_pct=max_pct,
                        timestamp=ts,
                    )
                )

        qty = int(order.quantity or 0)
        if qty <= 0:
            try:
                qty = int(amount / float(order.price) / 100) * 100 if float(order.price) > 0 else 0
            except Exception:
                qty = 0

        if qty <= 0:
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="invalid_quantity",
                rule_name="order.quantity",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks

        final_decision = Decision.APPROVE
        final_reason = "ok"
        final_rule = "risk.default"
        final = DecisionResult(
            decision=final_decision,
            reason=final_reason,
            rule_name=final_rule,
            max_position_pct=max_pct,
            timestamp=ts,
        )
        checks.append(final)
        self._audit(order, final, ts)
        return final, checks

    def _audit(self, order: Order, final: DecisionResult, ts: str) -> None:
        raw = getattr(final, "decision", None)
        decision = getattr(raw, "value", None) if raw is not None else None
        if decision is None:
            decision = str(raw or "")
        self.audit_log.append(
            {
                "timestamp": ts,
                "stock_code": order.stock_code,
                "direction": order.direction,
                "amount": float(order.amount),
                "price": float(order.price),
                "quantity": int(order.quantity),
                "decision": decision,
                "reason": getattr(final, "reason", ""),
                "rule_name": getattr(final, "rule_name", ""),
                "max_position_pct": float(getattr(final, "max_position_pct", 0.0) or 0.0),
            }
        )


def _decision_to_dict(d: Any) -> dict[str, Any]:
    raw = getattr(d, "decision", None)
    decision = getattr(raw, "value", None) if raw is not None else None
    if decision is None:
        decision = str(raw or "")
    return {
        "decision": decision,
        "reason": getattr(d, "reason", ""),
        "rule_name": getattr(d, "rule_name", ""),
        "max_position_pct": float(getattr(d, "max_position_pct", 0.0) or 0.0),
        "timestamp": getattr(d, "timestamp", ""),
    }


def _calc_suggestion(order: Any, final: Any) -> tuple[int, int]:
    raw = getattr(final, "decision", None)
    decision = getattr(raw, "value", None) if raw is not None else None
    if decision is None:
        decision = str(raw or "")
    decision = decision.upper()
    if decision == "WARN":
        pct = float(final.max_position_pct or 0)
        amt = max(0.0, float(order.amount) * pct)
        qty = int(amt / float(order.price) / 100) * 100 if order.price > 0 else 0
        return int(round(qty * float(order.price))), qty
    if decision == "APPROVE":
        return int(round(order.amount)), int(order.quantity)
    return 0, 0


def approve(payload: dict[str, Any]) -> dict[str, Any]:
    manager = _get_manager()
    order_in = payload.get("order") or {}
    portfolio_in = payload.get("portfolio") or {}
    context_in = payload.get("context") or {}
    order = Order(
        stock_code=str(order_in.get("stock_code") or ""),
        direction=str(order_in.get("direction") or "buy"),
        amount=float(order_in.get("amount") or 0),
        price=float(order_in.get("price") or 0),
        quantity=int(order_in.get("quantity") or 0),
    )
    portfolio = {
        "total_asset": float(portfolio_in.get("total_asset") or 0),
        "prices": dict(portfolio_in.get("prices") or {}),
        "atr": dict(portfolio_in.get("atr") or {}),
    }
    context = {"news_text": str(context_in.get("news_text") or "")}
    final, checks = manager.approve_verbose(order, portfolio, context)
    suggested_amount, suggested_quantity = _calc_suggestion(order, final)
    base = _decision_to_dict(final)
    return {
        **base,
        "suggested_amount": int(suggested_amount),
        "suggested_quantity": int(suggested_quantity),
        "checks": [_decision_to_dict(x) for x in checks],
    }


def audit(last_n: int = 200) -> dict[str, Any]:
    manager = _get_manager()
    n = max(1, min(int(last_n), 2000))
    return {"items": list(manager.audit_log[-n:])}


def status() -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_summary()

