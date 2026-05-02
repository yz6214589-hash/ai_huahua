from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    ApproveRequest,
    CheckAtrStopRequest,
    RegisterPositionRequest,
    RemovePositionRequest,
    RiskDecisionOut,
    StartDayRequest,
    TradeCompleteRequest,
    UpdateMacroRequest,
)
from .risk_engine import Decision, Order, RiskDecision, RiskManager


@dataclass
class _KirsState:
    kris: RiskManager


def _decision_to_dict(d: RiskDecision) -> dict[str, Any]:
    return {
        "decision": d.decision.value,
        "reason": d.reason,
        "rule_name": d.rule_name,
        "max_position_pct": float(d.max_position_pct),
        "timestamp": d.timestamp,
    }


def _calc_suggestion(order: Order, final: RiskDecision) -> tuple[int, int]:
    if final.decision == Decision.WARN:
        pct = float(final.max_position_pct or 0)
        amt = max(0.0, float(order.amount) * pct)
        qty = int(amt / float(order.price) / 100) * 100 if order.price > 0 else 0
        amt2 = int(round(qty * float(order.price)))
        return amt2, qty

    if final.decision in (Decision.APPROVE,):
        return int(round(order.amount)), int(order.quantity)

    return 0, 0


def create_app() -> FastAPI:
    app = FastAPI(title="Kirs API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.kirs_state = _KirsState(kris=RiskManager())

    @app.get("/")
    def root() -> dict[str, Any]:
        return {"name": "Kirs API", "ok": True, "docs": "/docs", "health": "/api/health"}

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True}

    @app.post("/api/kris/start-day")
    def start_day(req: StartDayRequest) -> dict[str, Any]:
        app.state.kirs_state.kris.start_day(req.start_nav)
        return {"ok": True}

    @app.post("/api/kris/update-macro")
    def update_macro(req: UpdateMacroRequest) -> dict[str, Any]:
        coeff = app.state.kirs_state.kris.macro.update_vix(req.vix)
        return {
            "ok": True,
            "vix": app.state.kirs_state.kris.macro.current_vix,
            "risk_level": app.state.kirs_state.kris.macro.risk_level,
            "coefficient": coeff,
        }

    @app.post("/api/kris/approve", response_model=RiskDecisionOut)
    def approve(req: ApproveRequest) -> RiskDecisionOut:
        order_in = req.order
        order = Order(
            stock_code=order_in.stock_code,
            direction=order_in.direction,
            amount=float(order_in.amount),
            price=float(order_in.price),
            quantity=int(order_in.quantity or 0),
        )
        portfolio = {
            "total_asset": float(req.portfolio.total_asset or 0),
            "prices": dict(req.portfolio.prices or {}),
            "atr": dict(req.portfolio.atr or {}),
        }
        context = {"news_text": (req.context.news_text if req.context else "")}

        final, checks = app.state.kirs_state.kris.approve_verbose(order, portfolio, context)
        suggested_amount, suggested_quantity = _calc_suggestion(order, final)

        return RiskDecisionOut(
            decision=final.decision.value,  # type: ignore[arg-type]
            reason=final.reason,
            rule_name=final.rule_name,
            max_position_pct=float(final.max_position_pct),
            suggested_amount=int(suggested_amount),
            suggested_quantity=int(suggested_quantity),
            timestamp=final.timestamp,
            checks=[_decision_to_dict(x) for x in checks],
        )

    @app.post("/api/kris/trade-complete")
    def trade_complete(req: TradeCompleteRequest) -> dict[str, Any]:
        d = app.state.kirs_state.kris.on_trade_complete(req.nav)
        return {"ok": True, "decision": _decision_to_dict(d) if d else None}

    @app.post("/api/kris/register-position")
    def register_position(req: RegisterPositionRequest) -> dict[str, Any]:
        app.state.kirs_state.kris.register_position(req.stock_code, req.entry_price, req.atr)
        return {"ok": True}

    @app.post("/api/kris/remove-position")
    def remove_position(req: RemovePositionRequest) -> dict[str, Any]:
        app.state.kirs_state.kris.remove_position(req.stock_code)
        return {"ok": True}

    @app.post("/api/kris/check-atr-stop")
    def check_atr_stop(req: CheckAtrStopRequest) -> dict[str, Any]:
        d = app.state.kirs_state.kris.check_atr_stop(req.stock_code, req.current_price)
        return {"ok": True, "decision": _decision_to_dict(d) if d else None}

    @app.get("/api/kris/audit")
    def audit(last_n: int = 200) -> dict[str, Any]:
        last_n = max(1, min(int(last_n or 200), 2000))
        items = list(app.state.kirs_state.kris.audit_log[-last_n:])
        return {"items": items}

    @app.get("/api/kris/status")
    def status() -> dict[str, Any]:
        return app.state.kirs_state.kris.get_summary()

    return app


app = create_app()
