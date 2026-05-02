from __future__ import annotations

import os


def test_mainforce_task_store_roundtrip(tmp_path):
    from zoe.app.mainforce.store import create_task, get_task, list_tasks, save_tasks

    path = str(tmp_path / "tasks.json")
    t = create_task(stock_code="600519.SH", company_name="贵州茅台", params={"n_samples_per_class": 3}, tasks_path=path)
    save_tasks(path, [t])
    tasks = list_tasks(path)
    assert len(tasks) == 1
    got = get_task(path, t.task_id)
    assert got is not None
    assert got.stock_code == "600519.SH"


def test_mainforce_run_generates_artifacts(tmp_path, monkeypatch):
    from zoe.app.mainforce.engine import run_mainforce_job

    out_dir = tmp_path / "out"
    os.makedirs(out_dir, exist_ok=True)

    monkeypatch.setattr("zoe.app.mainforce.engine.plot_feature_radar", lambda *a, **k: str(out_dir / "radar.png"))
    monkeypatch.setattr("zoe.app.mainforce.engine.plot_typical_patterns", lambda *a, **k: str(out_dir / "patterns.png"))
    monkeypatch.setattr("zoe.app.mainforce.engine.plot_confusion_matrix", lambda *a, **k: str(out_dir / "confusion.png"))
    monkeypatch.setattr(
        "zoe.app.mainforce.engine.plot_feature_importance", lambda *a, **k: str(out_dir / "feature_importance.png")
    )

    res = run_mainforce_job(output_dir=str(out_dir), n_samples_per_class=3, seed=1, n_ticks=50, window=20)
    assert "train_acc" in res
    assert "test_acc" in res
    assert "feature_importance" in res
