from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .models import JobDomain, JobRunResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return uuid4().hex


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_run(store_dir: str, run: JobRunResult) -> None:
    ensure_dir(store_dir)
    path = os.path.join(store_dir, f"{run.runId}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(run.model_dump(), f, ensure_ascii=False, indent=2)


def read_run(store_dir: str, run_id: str) -> dict[str, Any] | None:
    path = os.path.join(store_dir, f"{run_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_runs(store_dir: str, domain: JobDomain | None, limit: int) -> list[dict[str, Any]]:
    if not os.path.isdir(store_dir):
        return []
    files = [f for f in os.listdir(store_dir) if f.endswith(".json")]
    out: list[dict[str, Any]] = []
    for fn in files:
        path = os.path.join(store_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        if domain is not None and obj.get("domain") != domain.value:
            continue
        out.append(obj)
    out.sort(key=lambda x: str(x.get("startedAt") or ""), reverse=True)
    return out[:limit]


def init_running(domain: JobDomain) -> JobRunResult:
    return JobRunResult(
        runId=new_run_id(),
        domain=domain,
        startedAt=_now_iso(),
        status="running",
        dataSourceFinal="unknown",
        fallbackChain=[],
        rowsWritten=0,
        itemsProcessed=0,
        failedItems=[],
        message=None,
    )

