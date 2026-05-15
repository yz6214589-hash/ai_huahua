from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Side(str, Enum):
    buy = "buy"
    sell = "sell"


class StrategyType(str, Enum):
    twap = "twap"
    vwap = "vwap"
    rl = "rl"


class CancelRetryRule(BaseModel):
    max_retries: int = Field(default=0, ge=0, le=20)
    wait_seconds: float = Field(default=2.0, ge=0.0, le=120.0)


class ExecutionConstraints(BaseModel):
    max_participation_rate: float = Field(default=0.1, gt=0.0, le=1.0)
    max_single_order_qty: int = Field(default=10_000, ge=100)
    cancel_retry: CancelRetryRule = Field(default_factory=CancelRetryRule)
    slippage_alert_bps: float = Field(default=50.0, ge=0.0, le=10_000.0)


class ExecutionTaskCreate(BaseModel):
    symbol: str
    side: Side
    total_qty: int = Field(ge=100)
    num_steps: int = Field(default=48, ge=1, le=390)
    strategy: StrategyType
    rl_model_path: str | None = None
    impact_eta: float = Field(default=0.1, ge=0.0, le=10.0)
    impact_gamma: float = Field(default=0.05, ge=0.0, le=10.0)
    adv: float | None = Field(default=None, gt=0.0)
    constraints: ExecutionConstraints = Field(default_factory=ExecutionConstraints)


class ExecutionTask(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    symbol: str
    side: Side
    total_qty: int
    num_steps: int
    strategy: StrategyType
    rl_model_path: str | None
    impact_eta: float
    impact_gamma: float
    adv: float
    constraints: ExecutionConstraints
    status: Literal["draft", "running", "stopped", "finished", "failed"]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

