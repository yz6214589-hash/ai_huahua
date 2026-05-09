from __future__ import annotations

from typing import Any
from uuid import uuid4

from datetime import datetime, timezone

from ai_quant_api.services.ethan.models import ExecutionTask, ExecutionTaskCreate
from ai_quant_api.services.ethan.store import InMemoryStore

_STORE = None


def _get_store():
    global _STORE
    if _STORE is not None:
        return _STORE
    _STORE = InMemoryStore()
    return _STORE


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_status() -> dict[str, Any]:
    return {"source": "ethan", "status": "ready", "features": ["tasks"], "mode": "embedded"}


def create_execution_task(payload: dict[str, Any]) -> dict[str, Any]:
    req = ExecutionTaskCreate(**payload)
    adv = float(req.adv or 2_000_000)
    task = ExecutionTask(
        id=uuid4().hex,
        symbol=req.symbol,
        side=req.side,
        total_qty=req.total_qty,
        num_steps=req.num_steps,
        strategy=req.strategy,
        rl_model_path=req.rl_model_path,
        impact_eta=req.impact_eta,
        impact_gamma=req.impact_gamma,
        adv=adv,
        constraints=req.constraints,
        status="draft",
        created_at=_now_iso(),
    )
    store = _get_store()
    store.put_task(task)
    return task.model_dump()


def list_execution_tasks() -> dict[str, Any]:
    store = _get_store()
    return {"items": [x.model_dump() for x in store.list_tasks()]}


def get_execution_task(task_id: str) -> dict[str, Any] | None:
    store = _get_store()
    task = store.get_task(task_id)
    if not task:
        return None
    return {"task": task.model_dump()}
