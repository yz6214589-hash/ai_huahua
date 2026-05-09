from fastapi.testclient import TestClient

from ai_quant_api.app import app
from ai_quant_api.api import reports as reports_api
import time


def test_reports_task_crud_and_view(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_REPORT_MYSQL_ENABLED", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_TASK_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AI_QUANT_REPORT_STORE_BOOTSTRAP", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AI_QUANT_REPORT_USE_LLM", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k1")
    monkeypatch.setattr(reports_api, "_generate_report_markdown", lambda model, stock_code, stock_name, use_rag=True: f"# {stock_code}\n")
    client = TestClient(app)

    create = client.post(
        "/api/reports/tasks",
        json={"model": "qwen-max", "stock_codes": ["600519"]},
    )
    assert create.status_code == 200
    task = (create.json() or {}).get("task") or {}
    task_id = task.get("task_id")
    assert task_id
    assert task.get("model") == "qwen-max"
    assert task.get("stock_codes") == ["600519"]
    assert task.get("status") in ("waiting", "running")
    assert task.get("finished_at") in (None, "")
    assert task.get("report_markdown") in (None, "")

    lst = client.get("/api/reports/tasks?limit=100")
    assert lst.status_code == 200
    tasks = (lst.json() or {}).get("tasks") or []
    assert any(x.get("task_id") == task_id for x in tasks)

    deadline = time.time() + 2.0
    final = None
    while time.time() < deadline:
        view = client.get(f"/api/reports/tasks/{task_id}/view")
        if view.status_code == 200:
            final = view
            break
        assert view.status_code in (409, 500)
        time.sleep(0.05)
    assert final is not None
    assert "600519" in (final.text or "")

    delete = client.delete(f"/api/reports/tasks/{task_id}")
    assert delete.status_code == 200
    assert delete.json().get("ok") is True


def test_reports_use_llm_enabled_without_key_still_generates(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_REPORT_MYSQL_ENABLED", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_TASK_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AI_QUANT_REPORT_STORE_BOOTSTRAP", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_USE_LLM", "1")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setattr(reports_api, "_dashscope_generate", lambda **_: (_ for _ in ()).throw(RuntimeError("missing env: DASHSCOPE_API_KEY")))
    client = TestClient(app)

    create = client.post(
        "/api/reports/tasks",
        json={"model": "deepseek", "stock_codes": ["002410.SZ"]},
    )
    assert create.status_code == 200
    task = (create.json() or {}).get("task") or {}
    task_id = task.get("task_id")
    assert task_id

    deadline = time.time() + 2.0
    final = None
    while time.time() < deadline:
        view = client.get(f"/api/reports/tasks/{task_id}/view")
        if view.status_code in (200, 500):
            final = view
            break
        assert view.status_code == 409
        time.sleep(0.05)
    assert final is not None
    assert final.status_code == 500
    text = final.text or ""
    assert ("DASHSCOPE" in text) or ("missing env" in text) or ("LLM" in text)


def test_reports_minmax_many_stocks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_REPORT_MYSQL_ENABLED", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_TASK_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AI_QUANT_REPORT_STORE_BOOTSTRAP", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AI_QUANT_REPORT_USE_LLM", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k1")
    monkeypatch.setattr(reports_api, "_generate_report_markdown", lambda model, stock_code, stock_name, use_rag=True: f"# {stock_code}\n")
    client = TestClient(app)

    codes = [f"6005{str(i).zfill(2)}" for i in range(1, 21)]
    create = client.post(
        "/api/reports/tasks",
        json={"model": "qwen-max", "stock_codes": codes},
    )
    assert create.status_code == 200
    task = (create.json() or {}).get("task") or {}
    task_id = task.get("task_id")
    assert task_id

    deadline = time.time() + 3.0
    final = None
    while time.time() < deadline:
        view = client.get(f"/api/reports/tasks/{task_id}/view")
        if view.status_code == 200:
            final = view
            break
        assert view.status_code in (409, 500)
        time.sleep(0.05)
    assert final is not None
    text = final.text or ""
    assert codes[0] in text
    assert codes[-1] in text


def test_reports_retry_failed_then_success(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_REPORT_MYSQL_ENABLED", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_TASK_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AI_QUANT_REPORT_STORE_BOOTSTRAP", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AI_QUANT_REPORT_USE_LLM", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k1")

    state = {"n": 0}

    def flappy(model: str, stock_code: str, stock_name: str, use_rag: bool = True) -> str:
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("boom")
        return f"# {stock_code}\n"

    monkeypatch.setattr(reports_api, "_generate_report_markdown", flappy)
    client = TestClient(app)

    create = client.post(
        "/api/reports/tasks",
        json={"model": "qwen-max", "stock_codes": ["600519"]},
    )
    assert create.status_code == 200
    task = (create.json() or {}).get("task") or {}
    task_id = task.get("task_id")
    assert task_id

    deadline = time.time() + 2.0
    failed = None
    while time.time() < deadline:
        view = client.get(f"/api/reports/tasks/{task_id}/view")
        if view.status_code == 500:
            failed = view
            break
        assert view.status_code in (409, 200)
        time.sleep(0.05)
    assert failed is not None

    retry = client.post(f"/api/reports/tasks/{task_id}/retry")
    assert retry.status_code == 200
    assert retry.json().get("ok") is True

    deadline2 = time.time() + 2.0
    final = None
    while time.time() < deadline2:
        view = client.get(f"/api/reports/tasks/{task_id}/view")
        if view.status_code == 200:
            final = view
            break
        assert view.status_code in (409, 500)
        time.sleep(0.05)
    assert final is not None
    assert "600519" in (final.text or "")


def test_reports_can_disable_rag_per_task(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_REPORT_MYSQL_ENABLED", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_TASK_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AI_QUANT_REPORT_STORE_BOOTSTRAP", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AI_QUANT_REPORT_USE_LLM", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k1")

    called = {"use_rag": None}

    def gen(model: str, stock_code: str, stock_name: str, use_rag: bool) -> str:
        called["use_rag"] = bool(use_rag)
        return f"# {stock_code}\n"

    monkeypatch.setattr(reports_api, "_generate_report_markdown", gen)
    client = TestClient(app)

    create = client.post(
        "/api/reports/tasks",
        json={"model": "qwen-max", "stock_codes": ["600519"], "use_rag": False},
    )
    assert create.status_code == 200
    task = (create.json() or {}).get("task") or {}
    task_id = task.get("task_id")
    assert task_id

    deadline = time.time() + 2.0
    final = None
    while time.time() < deadline:
        view = client.get(f"/api/reports/tasks/{task_id}/view")
        if view.status_code == 200:
            final = view
            break
        assert view.status_code in (409, 500)
        time.sleep(0.05)
    assert final is not None
    assert called["use_rag"] is False


def test_reports_saves_markdown_to_md_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_REPORT_MYSQL_ENABLED", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_TASK_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AI_QUANT_REPORT_STORE_BOOTSTRAP", "0")
    out_dir = tmp_path / "out"
    monkeypatch.setenv("AI_QUANT_REPORT_OUTPUT_DIR", str(out_dir))
    monkeypatch.setenv("AI_QUANT_REPORT_USE_LLM", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k1")
    monkeypatch.setattr(reports_api, "_generate_report_markdown", lambda model, stock_code, stock_name, use_rag=True: f"# {stock_code}\n")
    client = TestClient(app)

    create = client.post(
        "/api/reports/tasks",
        json={"model": "qwen-max", "stock_codes": ["600519"]},
    )
    assert create.status_code == 200
    task = (create.json() or {}).get("task") or {}
    task_id = task.get("task_id")
    assert task_id

    deadline = time.time() + 2.0
    final = None
    while time.time() < deadline:
        view = client.get(f"/api/reports/tasks/{task_id}/view")
        if view.status_code == 200:
            final = view
            break
        assert view.status_code in (409, 500)
        time.sleep(0.05)
    assert final is not None

    md = out_dir / f"{task_id}.md"
    assert md.exists()
    assert "600519" in md.read_text(encoding="utf-8")


def test_reports_failed_task_has_error_location(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_REPORT_MYSQL_ENABLED", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_TASK_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AI_QUANT_REPORT_STORE_BOOTSTRAP", "0")
    monkeypatch.setenv("AI_QUANT_REPORT_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("AI_QUANT_REPORT_USE_LLM", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "k1")

    def boom(model: str, stock_code: str, stock_name: str, use_rag: bool = True) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(reports_api, "_generate_report_markdown", boom)
    client = TestClient(app)

    create = client.post(
        "/api/reports/tasks",
        json={"model": "qwen-max", "stock_codes": ["600519"]},
    )
    assert create.status_code == 200
    task = (create.json() or {}).get("task") or {}
    task_id = task.get("task_id")
    assert task_id

    deadline = time.time() + 2.0
    failed = None
    while time.time() < deadline:
        view = client.get(f"/api/reports/tasks/{task_id}/view")
        if view.status_code == 500:
            failed = view
            break
        assert view.status_code in (409, 200)
        time.sleep(0.05)
    assert failed is not None

    tasks = (client.get("/api/reports/tasks?limit=50").json() or {}).get("tasks") or []
    item = [t for t in tasks if t.get("task_id") == task_id][0]
    assert item.get("error_location")
