from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import uuid4
import os
import json
from pathlib import Path
import re


@dataclass
class ReportTaskRecord:
    task_id: str
    model: str
    stock_codes: list[str]
    stock_names: list[str]
    use_rag: bool
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    error_location: str | None = None
    report_path: str | None = None
    report_markdown: str | None = None


_TASKS: dict[str, ReportTaskRecord] = {}
_LOCK = Lock()
_LOADED = False
_MYSQL_READY = False


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _store_dir() -> Path:
    env = str(os.getenv("AI_QUANT_REPORT_TASK_STORE_DIR", "") or "").strip()
    if env:
        return Path(env)
    return _project_root() / ".ai_quant" / "report_tasks"


def _task_path(task_id: str) -> Path:
    return _store_dir() / f"{task_id}.json"


def _mysql_enabled() -> bool:
    raw = str(os.getenv("AI_QUANT_REPORT_MYSQL_ENABLED", "1") or "").strip()
    return raw not in ("0", "false", "False")


def _to_mysql_dt(v: str | None) -> str | None:
    s = str(v or "").strip()
    if not s:
        return None
    if "T" in s:
        s = s.replace("T", " ")
    return s[:19]


def _ensure_mysql_table(conn) -> None:
    global _MYSQL_READY
    if _MYSQL_READY:
        return
    from ai_quant_api.db import execute

    sql = """
    CREATE TABLE IF NOT EXISTS ai_quant_report_tasks (
      task_id VARCHAR(64) NOT NULL,
      model VARCHAR(32) NOT NULL,
      stock_codes TEXT NULL,
      stock_names TEXT NULL,
      use_rag TINYINT(1) NOT NULL DEFAULT 1,
      status VARCHAR(16) NOT NULL,
      created_at DATETIME NOT NULL,
      started_at DATETIME NULL,
      finished_at DATETIME NULL,
      error_message TEXT NULL,
      error_location VARCHAR(256) NULL,
      report_path VARCHAR(512) NULL,
      updated_at DATETIME NOT NULL,
      PRIMARY KEY (task_id),
      KEY idx_status (status),
      KEY idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    execute(conn, sql)
    _MYSQL_READY = True


def _mysql_upsert(rec: ReportTaskRecord) -> None:
    if not _mysql_enabled():
        return
    try:
        from ai_quant_api.db import connect, execute, load_mysql_config

        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return
    try:
        _ensure_mysql_table(conn)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
        INSERT INTO ai_quant_report_tasks
          (task_id, model, stock_codes, stock_names, use_rag, status, created_at, started_at, finished_at, error_message, error_location, report_path, updated_at)
        VALUES
          (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          model=VALUES(model),
          stock_codes=VALUES(stock_codes),
          stock_names=VALUES(stock_names),
          use_rag=VALUES(use_rag),
          status=VALUES(status),
          created_at=VALUES(created_at),
          started_at=VALUES(started_at),
          finished_at=VALUES(finished_at),
          error_message=VALUES(error_message),
          error_location=VALUES(error_location),
          report_path=VALUES(report_path),
          updated_at=VALUES(updated_at)
        """
        execute(
            conn,
            sql,
            (
                rec.task_id,
                rec.model or "",
                json.dumps(rec.stock_codes or [], ensure_ascii=False),
                json.dumps(rec.stock_names or [], ensure_ascii=False),
                1 if rec.use_rag else 0,
                rec.status or "",
                _to_mysql_dt(rec.created_at) or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                _to_mysql_dt(rec.started_at),
                _to_mysql_dt(rec.finished_at),
                rec.error_message,
                rec.error_location,
                rec.report_path,
                now,
            ),
        )
    except Exception:
        return
    finally:
        conn.close()


def _mysql_delete(task_id: str) -> None:
    if not _mysql_enabled():
        return
    try:
        from ai_quant_api.db import connect, execute, load_mysql_config

        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return
    try:
        _ensure_mysql_table(conn)
        execute(conn, "DELETE FROM ai_quant_report_tasks WHERE task_id=%s", (task_id,))
    except Exception:
        return
    finally:
        conn.close()


def _load_once() -> None:
    global _LOADED
    if _LOADED:
        return
    _TASKS.clear()
    root = _store_dir()
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)

    for p in root.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        tid = str(data.get("task_id") or "").strip()
        if not tid:
            continue
        rec = ReportTaskRecord(
            task_id=tid,
            model=str(data.get("model") or ""),
            stock_codes=list(data.get("stock_codes") or []),
            stock_names=list(data.get("stock_names") or []),
            use_rag=bool(data.get("use_rag", True)),
            status=str(data.get("status") or "waiting"),
            created_at=str(data.get("created_at") or now_iso()),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            error_message=data.get("error_message"),
            error_location=data.get("error_location"),
            report_path=data.get("report_path"),
            report_markdown=data.get("report_markdown"),
        )
        _TASKS[tid] = rec

    try:
        bootstrap = str(os.getenv("AI_QUANT_REPORT_STORE_BOOTSTRAP", "1")).strip() not in ("0", "false", "False")
    except Exception:
        bootstrap = True
    if bootstrap:
        _bootstrap_from_outputs_and_log()
    _LOADED = True


def _bootstrap_from_outputs_and_log() -> None:
    primary_root = _project_root()
    candidate_roots = [primary_root]
    try:
        parent = primary_root.parent
        if parent and parent not in candidate_roots:
            candidate_roots.append(parent)
    except Exception:
        pass

    def _iso_from_mtime(path: Path) -> str:
        try:
            ts = path.stat().st_mtime
            return datetime.fromtimestamp(ts).isoformat(timespec="seconds")
        except Exception:
            return now_iso()

    for project_root in candidate_roots:
        outputs_dir = project_root / ".ai_quant" / "report_outputs"
        log_file = project_root / ".ai_quant" / "reports_worker.log"

        if outputs_dir.exists():
            for md in outputs_dir.glob("*.md"):
                tid = md.stem.strip()
                if not tid:
                    continue
                try:
                    content = md.read_text(encoding="utf-8")
                except Exception:
                    content = ""
                created = _iso_from_mtime(md)
                if tid in _TASKS:
                    rec = _TASKS[tid]
                    if rec.status == "success" and (rec.report_markdown is None or str(rec.report_markdown) == ""):
                        if content.strip():
                            rec.report_markdown = content
                            rec.started_at = rec.started_at or created
                            rec.finished_at = rec.finished_at or created
                            _persist(rec, mysql=False)
                        else:
                            rec.status = "failed"
                            rec.error_message = rec.error_message or "report file empty"
                            _persist(rec, mysql=False)
                    continue

                rec2 = ReportTaskRecord(
                    task_id=tid,
                    model="",
                    stock_codes=[],
                    stock_names=[],
                    use_rag=True,
                    status="success" if content.strip() else "failed",
                    created_at=created,
                    started_at=created,
                    finished_at=created,
                    error_message=None if content.strip() else "report file empty",
                    error_location=None,
                    report_path=str(md),
                    report_markdown=content if content.strip() else None,
                )
                _TASKS[tid] = rec2
                _persist(rec2, mysql=False)

        if log_file.exists():
            try:
                lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                lines = []

            re_failed = re.compile(r"^\[(?P<ts>[0-9:\-\s]+)\].*?\[reports\]\s+task_failed\s+task_id=(?P<id>[0-9a-f]{16,64})\s+(?P<msg>.*)$")
            re_enter = re.compile(r"^\[(?P<ts>[0-9:\-\s]+)\].*?\[reports\]\s+_generate_report_markdown enter\s+model=(?P<model>\S+)\s+stock_code=(?P<code>\S+)\s+stock_name=(?P<name>\S+)(?:\s+.*)?$")

            last_meta_by_task: dict[str, dict[str, str]] = {}
            for ln in lines:
                m2 = re_enter.search(ln)
                if m2:
                    meta = {"model": m2.group("model"), "code": m2.group("code"), "name": m2.group("name"), "ts": m2.group("ts").strip()}
                    last_meta_by_task["_last"] = meta
                    continue

                m = re_failed.search(ln)
                if not m:
                    continue
                tid = m.group("id")
                msg = (m.group("msg") or "").strip()
                ts = m.group("ts").strip()
                meta = last_meta_by_task.get("_last") or {}
                created = ts.replace(" ", "T") if len(ts) >= 10 else now_iso()
                if tid in _TASKS:
                    rec = _TASKS[tid]
                    changed = False
                    if (not rec.model) and str(meta.get("model") or "").strip():
                        rec.model = str(meta.get("model") or "")
                        changed = True
                    if (not rec.stock_codes) and str(meta.get("code") or "").strip():
                        rec.stock_codes = [str(meta.get("code") or "")]
                        changed = True
                    if (not rec.stock_names) and str(meta.get("name") or "").strip():
                        rec.stock_names = [str(meta.get("name") or "")]
                        changed = True
                    if rec.status == "success" and (rec.report_markdown is None or str(rec.report_markdown) == ""):
                        rec.status = "failed"
                        rec.error_message = rec.error_message or "report empty"
                        changed = True
                    if rec.status != "failed":
                        rec.status = "failed"
                        changed = True
                    if not rec.error_message:
                        rec.error_message = msg or "failed"
                        changed = True
                    if changed:
                        rec.created_at = rec.created_at or created
                        rec.started_at = created
                        rec.finished_at = created
                        _persist(rec, mysql=False)
                    continue

                rec2 = ReportTaskRecord(
                    task_id=tid,
                    model=str(meta.get("model") or ""),
                    stock_codes=[str(meta.get("code") or "")] if str(meta.get("code") or "").strip() else [],
                    stock_names=[str(meta.get("name") or "")] if str(meta.get("name") or "").strip() else [],
                    use_rag=True,
                    status="failed",
                    created_at=created,
                    started_at=created,
                    finished_at=created,
                    error_message=msg or "failed",
                    error_location=None,
                    report_path=None,
                    report_markdown=None,
                )
                _TASKS[tid] = rec2
                _persist(rec2, mysql=False)


def _persist(rec: ReportTaskRecord, *, mysql: bool = True) -> None:
    root = _store_dir()
    root.mkdir(parents=True, exist_ok=True)
    p = _task_path(rec.task_id)
    tmp = p.with_name(f".{p.name}.tmp")
    tmp.write_text(json.dumps(asdict(rec), ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(p)
    if mysql:
        _mysql_upsert(rec)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_task(model: str, stock_codes: list[str], stock_names: list[str], use_rag: bool = True) -> ReportTaskRecord:
    task_id = uuid4().hex
    rec = ReportTaskRecord(
        task_id=task_id,
        model=model,
        stock_codes=list(stock_codes),
        stock_names=list(stock_names),
        use_rag=bool(use_rag),
        status="waiting",
        created_at=now_iso(),
    )
    with _LOCK:
        _load_once()
        _TASKS[task_id] = rec
        _persist(rec, mysql=True)
    return rec


def update_task(task_id: str, **patch: Any) -> ReportTaskRecord | None:
    with _LOCK:
        _load_once()
        rec = _TASKS.get(task_id)
        if rec is None:
            return None
        for k, v in patch.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        _persist(rec, mysql=True)
        return rec


def get_task(task_id: str) -> ReportTaskRecord | None:
    with _LOCK:
        _load_once()
        return _TASKS.get(task_id)


def delete_task(task_id: str) -> bool:
    with _LOCK:
        _load_once()
        ok = _TASKS.pop(task_id, None) is not None
        if ok:
            try:
                _task_path(task_id).unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass
            _mysql_delete(task_id)
        return ok


def list_tasks() -> list[dict[str, Any]]:
    with _LOCK:
        _load_once()
        items = list(_TASKS.values())
    items.sort(key=lambda x: x.created_at, reverse=True)
    return [asdict(x) for x in items]
