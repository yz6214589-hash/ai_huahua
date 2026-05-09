from __future__ import annotations

from pathlib import Path

from ai_quant_api.services.ethan.integration import create_execution_task, list_execution_tasks


def test_ethan_integration_has_no_external_dependency() -> None:
    p = Path(__file__).resolve().parents[1] / "ai_quant_api" / "services" / "ethan" / "integration.py"
    text = p.read_text(encoding="utf-8")
    assert "ethan_api" not in text
    assert "sys.path.insert" not in text


def test_create_execution_task_persists_in_store() -> None:
    task = create_execution_task(
        {
            "symbol": "000001.SZ",
            "side": "buy",
            "total_qty": 1000,
            "num_steps": 4,
            "strategy": "twap",
        }
    )
    assert task.get("id")
    assert task.get("status") == "draft"
    items = list_execution_tasks().get("items") or []
    assert any(x.get("id") == task["id"] for x in items)

