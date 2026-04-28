from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StrategyInstance:
    instance_id: str
    strategy_id: str
    name: str
    params: dict[str, Any]


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


def load_instances(path: str) -> list[StrategyInstance]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f) or []
    out: list[StrategyInstance] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        instance_id = str(item.get("instance_id", "")).strip()
        strategy_id = str(item.get("strategy_id", "")).strip()
        name = str(item.get("name", "")).strip()
        params = item.get("params") if isinstance(item.get("params"), dict) else {}
        if instance_id and strategy_id and name:
            out.append(StrategyInstance(instance_id=instance_id, strategy_id=strategy_id, name=name, params=params))
    normalized, changed = normalize_instances(out)
    if changed:
        save_instances(path, normalized)
    return normalized


def normalize_instances(instances: list[StrategyInstance]) -> tuple[list[StrategyInstance], bool]:
    if not instances:
        return [], False

    ids = [s.instance_id for s in instances]
    all_numeric = all(i.isdigit() and int(i) > 0 for i in ids)
    unique = len(set(ids)) == len(ids)
    if all_numeric and unique:
        want = {str(i) for i in range(1, len(ids) + 1)}
        if set(ids) == want:
            return instances, False

    normalized: list[StrategyInstance] = []
    for idx, s in enumerate(instances, start=1):
        normalized.append(
            StrategyInstance(instance_id=str(idx), strategy_id=s.strategy_id, name=s.name, params=s.params)
        )
    return normalized, True


def save_instances(path: str, instances: list[StrategyInstance]) -> None:
    _ensure_parent(path)
    data = [
        {"instance_id": s.instance_id, "strategy_id": s.strategy_id, "name": s.name, "params": s.params}
        for s in instances
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

