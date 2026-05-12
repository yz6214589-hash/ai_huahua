from __future__ import annotations

import json
import os
from typing import Any, Iterator

import requests


def _base() -> str:
    return os.getenv("AI_QUANT_API_BASE", "http://localhost:8000").rstrip("/")


def get_status() -> dict[str, Any]:
    r = requests.get(f"{_base()}/api/agent/status", timeout=10)
    r.raise_for_status()
    return r.json()


def get_tools() -> list[dict[str, Any]]:
    r = requests.get(f"{_base()}/api/agent/tools", timeout=10)
    r.raise_for_status()
    return r.json().get("items", [])


def get_agent_runs(limit: int = 20) -> list[dict[str, Any]]:
    r = requests.get(f"{_base()}/api/agent/runs", timeout=10)
    r.raise_for_status()
    runs = r.json().get("runs", [])
    return list(runs)[-limit:]


def stream_agent(user_input: str) -> Iterator[dict[str, Any]]:
    with requests.post(
        f"{_base()}/api/agent/stream",
        json={"input": user_input},
        stream=True,
        timeout=120,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        resp.raise_for_status()
        ev_type = ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if line.startswith("event:"):
                ev_type = line[6:].strip()
                continue
            if line.startswith("data:"):
                try:
                    payload = json.loads(line[5:].strip())
                except Exception:
                    continue
                yield {**payload, "_event": ev_type}


def list_conversations() -> list[dict[str, Any]]:
    r = requests.get(f"{_base()}/api/conversations", timeout=10)
    r.raise_for_status()
    return r.json()


def create_conversation(title: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if title:
        body["title"] = title
    r = requests.post(f"{_base()}/api/conversations", json=body, timeout=20)
    r.raise_for_status()
    return r.json()


def get_conversation(conv_id: str) -> dict[str, Any]:
    r = requests.get(f"{_base()}/api/conversations/{conv_id}", timeout=20)
    r.raise_for_status()
    return r.json()


def delete_conversation(conv_id: str) -> None:
    r = requests.delete(f"{_base()}/api/conversations/{conv_id}", timeout=20)
    r.raise_for_status()


def add_message(conv_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"role": role, "content": content}
    if metadata is not None:
        body["metadata"] = metadata
    r = requests.post(f"{_base()}/api/conversations/{conv_id}/messages", json=body, timeout=20)
    r.raise_for_status()
    return r.json()
