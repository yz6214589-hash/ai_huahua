"""
工作流模块

包含：
- morning_brief_graph: 晨会简报工作流
- trading_team_graph: 交易团队工作流
- trading_state: 交易团队状态定义
"""

from workflow.morning_brief_graph import build_graph as build_morning_graph
from workflow.trading_team_graph import build_trading_graph, run_trading_workflow
from workflow.trading_state import (
    InvestmentView,
    RiskVerdict,
    TradeResult,
    TradeSignal,
    TradingState,
)

__all__ = [
    "build_morning_graph",
    "build_trading_graph",
    "run_trading_workflow",
    "InvestmentView",
    "RiskVerdict",
    "TradeResult",
    "TradeSignal",
    "TradingState",
]
