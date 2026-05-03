from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from threading import Lock


@dataclass
class AgentRunRecord:
    run_id: str
    input: str
    route: str
    created_at: str


_RUNS: list[AgentRunRecord] = []
_LOCK = Lock()


def append_run(record: AgentRunRecord) -> None:
    with _LOCK:
        _RUNS.insert(0, record)
        del _RUNS[50:]


def list_runs() -> list[dict[str, str]]:
    with _LOCK:
        return [asdict(x) for x in _RUNS]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
