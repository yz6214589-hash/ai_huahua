from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ai_quant_api.services.ceo.morning_brief import run_morning_workflow

def build_graph():
    graph = StateGraph(dict)

    def collect(state: dict[str, Any]) -> dict[str, Any]:
        payload = dict(state)
        if "industry_level" not in payload:
            payload["industry_level"] = 2
        if "top_n_industries" not in payload:
            payload["top_n_industries"] = 5
        if "top_n_stocks" not in payload:
            payload["top_n_stocks"] = 5
        if "lookback_days" not in payload:
            payload["lookback_days"] = 90
        if "sample_stocks" not in payload:
            payload["sample_stocks"] = 20
        if "messages" not in payload:
            payload["messages"] = []
        if "trigger_time" not in payload:
            payload["trigger_time"] = None
        if "input" in payload and "end_date" not in payload:
            pass
        return payload

    def run(state: dict[str, Any]) -> dict[str, Any]:
        return run_morning_workflow(state)

    graph.add_node("collect", collect)
    graph.add_node("run", run)
    graph.add_edge(START, "collect")
    graph.add_edge("collect", "run")
    graph.add_edge("run", END)
    return graph.compile()
