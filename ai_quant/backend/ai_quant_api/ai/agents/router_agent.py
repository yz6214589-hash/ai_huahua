from __future__ import annotations

from typing import Any


def route_intent(user_input: str) -> dict[str, Any]:
    text = user_input.strip()
    if not text:
        return {"target": "none", "reason": "empty_input"}
    if "晨会" in text:
        return {"target": "graph:morning_brief", "reason": "matched_keyword"}
    return {"target": "tool:quant_assistant", "reason": "default_route"}
