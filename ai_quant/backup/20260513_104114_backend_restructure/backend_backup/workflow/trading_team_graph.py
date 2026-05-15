"""
交易团队工作流图 (LangGraph)

团队成员：
- Charles: 投研情报官（基本面分析）
- Zoe: 信号官（技术信号）
- Kris: 风控官（风险控制）
- Human: 人工审批（人在回路）
- Trader: 交易执行（订单执行）

工作流图：
    START
      v
    charles  (投研)
      v
    zoe      (信号)
      v
    kris     (风控)
      v
    (kris approve?) -- no --> zoe_retry -> zoe
      v yes
    human    (人工审批)
      v
    (human approved?) -- no --> END
      v yes
    trader   (下单)
      v
    END
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from workflow.nodes import charles_node, zoe_node, kris_node, human_review_node, trader_node
from workflow.trading_state import TradingState


def route_after_kris(state: TradingState) -> str:
    """风控之后往哪走"""
    verdict = state.get("risk_verdict", {})
    retry = int(state.get("retry_count", 0))
    max_retry = int(state.get("max_retry", 2))
    decision = verdict.get("decision", "approve")

    if decision in ("halt", "reject"):
        if retry >= max_retry:
            print(f"[Graph] Kris 连续否决达上限 ({retry}/{max_retry})，终止流程")
            return END
        print(f"[Graph] Kris 否决，重试 {retry + 1}/{max_retry} -> 回到 Zoe")
        return "zoe_retry"
    return "human"


def route_after_human(state: TradingState) -> str:
    """人工审批之后往哪走"""
    approved = state.get("approved", False)
    if approved:
        return "trader"
    return END


def zoe_retry_bump(state: TradingState) -> dict:
    """重试中转节点：累加 retry_count"""
    return {"retry_count": int(state.get("retry_count", 0)) + 1}


def build_trading_graph():
    """构建交易团队工作流图"""
    graph = StateGraph(TradingState)

    graph.add_node("charles", charles_node)
    graph.add_node("zoe", zoe_node)
    graph.add_node("zoe_retry", zoe_retry_bump)
    graph.add_node("kris", kris_node)
    graph.add_node("human", human_review_node)
    graph.add_node("trader", trader_node)

    graph.add_edge(START, "charles")
    graph.add_edge("charles", "zoe")
    graph.add_edge("zoe", "kris")

    graph.add_conditional_edges(
        "kris",
        route_after_kris,
        {"zoe_retry": "zoe_retry", "human": "human", END: END},
    )
    graph.add_edge("zoe_retry", "zoe")

    graph.add_conditional_edges(
        "human",
        route_after_human,
        {"trader": "trader", END: END},
    )
    graph.add_edge("trader", END)

    return graph.compile()


def run_trading_workflow(
    stock_code: str,
    capital: float = 100000.0,
    user_question: str = "",
    max_retry: int = 2,
) -> dict[str, Any]:
    """运行交易团队工作流"""
    graph = build_trading_graph()
    initial_state: TradingState = {
        "stock_code": stock_code,
        "capital": capital,
        "user_question": user_question,
        "retry_count": 0,
        "max_retry": max_retry,
        "messages": [],
    }
    result = graph.invoke(initial_state)
    return dict(result)


__all__ = ["build_trading_graph", "run_trading_workflow"]
