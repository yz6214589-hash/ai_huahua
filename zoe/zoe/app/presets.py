from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Preset:
    preset_id: str
    strategy_id: str
    name: str
    params: dict[str, Any]


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


def load_presets(path: str) -> list[Preset]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f) or []
    presets: list[Preset] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        preset_id = str(item.get("preset_id", "")).strip()
        strategy_id = str(item.get("strategy_id", "")).strip()
        name = str(item.get("name", "")).strip()
        params = item.get("params") if isinstance(item.get("params"), dict) else {}
        if preset_id and strategy_id and name:
            presets.append(Preset(preset_id=preset_id, strategy_id=strategy_id, name=name, params=params))
    return presets


def save_presets(path: str, presets: list[Preset]) -> None:
    _ensure_parent(path)
    data = [
        {"preset_id": p.preset_id, "strategy_id": p.strategy_id, "name": p.name, "params": p.params} for p in presets
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

