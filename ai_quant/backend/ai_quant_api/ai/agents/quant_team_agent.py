from __future__ import annotations

from typing import Any


def run_quant_assistant(user_input: str) -> dict[str, Any]:
    return {
        "message": f"已接收任务：{user_input}",
        "modules": ["charles", "zoe", "ethan", "kris", "ceo"],
    }
