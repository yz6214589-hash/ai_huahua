from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph


def build_graph():
    g = StateGraph(dict)

    def validate(state: dict[str, Any]) -> dict[str, Any]:
        task = state.get("task") or {}
        if not task.get("symbol") or not task.get("total_qty"):
            return {"ok": False, "error": "invalid_task"}
        return {"ok": True}

    def plan(state: dict[str, Any]) -> dict[str, Any]:
        task = state.get("task") or {}
        return {"plan": {"strategy": task.get("strategy"), "num_steps": task.get("num_steps")}}

    def done(state: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ready"}

    def route(state: dict[str, Any]) -> str:
        return "plan" if state.get("ok") else END

    g.add_node("validate", validate)
    g.add_node("plan", plan)
    g.add_node("done", done)

    g.add_edge(START, "validate")
    g.add_conditional_edges("validate", route, {"plan": "plan", END: END})
    g.add_edge("plan", "done")
    g.add_edge("done", END)

    return g.compile()

