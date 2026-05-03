from __future__ import annotations

from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph


def build_graph():
    graph = StateGraph(dict)

    def collect(state: dict[str, Any]) -> dict[str, Any]:
        return {"input": state.get("input", "今日晨会")}

    def summarize(state: dict[str, Any]) -> dict[str, Any]:
        text = str(state.get("input", "今日晨会"))
        return {
            "summary": f"晨会已生成：{text}",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }

    graph.add_node("collect", collect)
    graph.add_node("summarize", summarize)
    graph.add_edge(START, "collect")
    graph.add_edge("collect", "summarize")
    graph.add_edge("summarize", END)
    return graph.compile()
