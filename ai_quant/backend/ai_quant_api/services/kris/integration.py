from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


_KRIS_MANAGER = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _ensure_kris_import_path() -> None:
    p = str(_project_root() / "kris" / "api")
    if p not in sys.path:
        sys.path.insert(0, p)


def _get_manager():
    global _KRIS_MANAGER
    if _KRIS_MANAGER is not None:
        return _KRIS_MANAGER
    _ensure_kris_import_path()
    from kris_api.risk_engine import RiskManager  # type: ignore

    _KRIS_MANAGER = RiskManager()
    return _KRIS_MANAGER


def _decision_to_dict(d: Any) -> dict[str, Any]:
    return {
        "decision": d.decision.value,
        "reason": d.reason,
        "rule_name": d.rule_name,
        "max_position_pct": float(d.max_position_pct),
        "timestamp": d.timestamp,
    }


def _calc_suggestion(order: Any, final: Any) -> tuple[int, int]:
    _ensure_kris_import_path()
    from kris_api.risk_engine import Decision  # type: ignore

    if final.decision == Decision.WARN:
        pct = float(final.max_position_pct or 0)
        amt = max(0.0, float(order.amount) * pct)
        qty = int(amt / float(order.price) / 100) * 100 if order.price > 0 else 0
        return int(round(qty * float(order.price))), qty
    if final.decision == Decision.APPROVE:
        return int(round(order.amount)), int(order.quantity)
    return 0, 0


def approve(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_kris_import_path()
    from kris_api.risk_engine import Order  # type: ignore

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
    return {
        "decision": final.decision.value,
        "reason": final.reason,
        "rule_name": final.rule_name,
        "max_position_pct": float(final.max_position_pct),
        "suggested_amount": int(suggested_amount),
        "suggested_quantity": int(suggested_quantity),
        "timestamp": final.timestamp,
        "checks": [_decision_to_dict(x) for x in checks],
    }


def audit(last_n: int = 200) -> dict[str, Any]:
    manager = _get_manager()
    n = max(1, min(int(last_n), 2000))
    return {"items": list(manager.audit_log[-n:])}


def status() -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_summary()
