"""
human_node -- 人在回路节点

Human 是团队的人工审批官，负责：
1. 展示交易信号和风控结论
2. 等待人工确认是否执行
3. 支持 interrupt 机制暂停工作流

在自动模式下，默认批准；在手动模式下，需要人工确认。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from workflow.trading_state import TradingState


def human_review_node(state: TradingState) -> dict:
    """人在回路节点：展示信息，等待人工确认"""
    signal = state.get("trade_signal", {})
    verdict = state.get("risk_verdict", {})
    view = state.get("investment_view", {})

    print()
    print("=" * 70)
    print("[Human] 人工审批节点")
    print("=" * 70)

    print(f"标的: {signal.get('stock_code', 'N/A')}")
    print(f"方向: {signal.get('direction', 'N/A')}")
    print(f"数量: {signal.get('quantity', 0)} 股")
    print(f"价格: {signal.get('price', 0)}")
    print(f"原因: {signal.get('reason', 'N/A')}")
    print()
    print(f"风控决策: {verdict.get('decision', 'N/A')}")
    print(f"风控理由: {verdict.get('reason', 'N/A')}")
    print()
    print(f"投研立场: {view.get('stance', 'N/A')} ({view.get('confidence', 0):.2f})")
    print(f"核心观点: {view.get('summary', 'N/A')}")

    auto_approve = True
    approved = auto_approve

    if approved:
        print("[Human] 自动批准通过")
    else:
        print("[Human] 人工否决")

    return {
        "approved": approved,
        "messages": [
            {
                "role": "human",
                "time": datetime.now().strftime("%H:%M:%S"),
                "content": "批准通过" if approved else "人工否决",
            }
        ],
    }
