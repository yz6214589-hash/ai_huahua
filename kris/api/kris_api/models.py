from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


DecisionStr = Literal["approve", "warn", "reject", "halt"]


class OrderIn(BaseModel):
    stock_code: str
    direction: Literal["buy", "sell"]
    amount: float = Field(gt=0)
    price: float = Field(gt=0)
    quantity: int = 0


class PortfolioIn(BaseModel):
    total_asset: float = 0
    prices: Dict[str, float] = Field(default_factory=dict)
    atr: Dict[str, float] = Field(default_factory=dict)


class ContextIn(BaseModel):
    news_text: str = ""


class ApproveRequest(BaseModel):
    order: OrderIn
    portfolio: PortfolioIn
    context: Optional[ContextIn] = None


class RiskDecisionOut(BaseModel):
    decision: DecisionStr
    reason: str
    rule_name: str
    max_position_pct: float = 1.0
    suggested_amount: int = 0
    suggested_quantity: int = 0
    timestamp: str
    checks: list[dict[str, Any]] = Field(default_factory=list)


class StartDayRequest(BaseModel):
    start_nav: float = Field(gt=0)


class UpdateMacroRequest(BaseModel):
    vix: float = Field(ge=0)


class TradeCompleteRequest(BaseModel):
    nav: float = Field(gt=0)


class RegisterPositionRequest(BaseModel):
    stock_code: str
    entry_price: float = Field(gt=0)
    atr: float = Field(gt=0)


class RemovePositionRequest(BaseModel):
    stock_code: str


class CheckAtrStopRequest(BaseModel):
    stock_code: str
    current_price: float = Field(gt=0)

