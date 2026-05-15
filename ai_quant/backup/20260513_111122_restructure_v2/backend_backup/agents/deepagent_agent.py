from __future__ import annotations

from typing import Any

from ai.deepagent_engine import run_deepagent


def run_agent(user_input: str, *, thread_id: str = "default") -> dict[str, Any]:
    res = run_deepagent(user_input, thread_id=thread_id)
    return {"text": res.text, "steps": res.steps}
