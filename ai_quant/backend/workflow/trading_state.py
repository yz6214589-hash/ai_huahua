"""
交易团队工作流状态定义

LangGraph 的精髓是 "State as a contract"：
  每个节点读取它关心的字段，写回它产出的字段；
  字段名一旦稳定，节点之间就完全解耦，可以独立替换实现。

约定字段所有权：
  Charles 写 investment_view
  Zoe     写 trade_signal
  Kris    写 risk_verdict
  Human   写 approved
  Trader  写 trade_result
  公共    retry_count / messages（每个节点都可 append 一条审计日志）
"""

from __future__ import annotations

from typing import Annotated, Optional, TypedDict
from operator import add


class InvestmentView(TypedDict, total=False):
    """Charles 的投研观点"""
    stance: str
    confidence: float
    summary: str
    catalysts: list
    risks: list
    raw_report: str
    report_md_path: str
    report_html_path: str


class TradeSignal(TypedDict, total=False):
    """Zoe 的交易信号"""
    stock_code: str
    direction: str
    quantity: int
    price: float
    reason: str
    strategy: str
    latest_signal: str
    latest_close: float
    backtest_winrate: float
    backtest_total_return: float


class RiskVerdict(TypedDict, total=False):
    """Kris 的风控决议"""
    decision: str
    is_approved: bool
    reason: str
    rule_name: str
    suggested_max_pct: float


class TradeResult(TypedDict, total=False):
    """Trader 的下单回执"""
    dry_run: bool
    order_id: Optional[int]
    submitted_at: str
    note: str


class TradingState(TypedDict, total=False):
    stock_code: str
    capital: float
    user_question: str

    investment_view: InvestmentView
    trade_signal: TradeSignal
    risk_verdict: RiskVerdict
    approved: Optional[bool]
    trade_result: TradeResult

    retry_count: int
    max_retry: int

    messages: Annotated[list, add]
