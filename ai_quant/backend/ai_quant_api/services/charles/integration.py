from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_quant_api.db import connect, load_mysql_config, query_dict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def get_job_store_dir() -> str:
    env = os.getenv("AI_QUANT_CHARLES_JOB_STORE_DIR", "").strip()
    if env:
        return env
    return str(_project_root() / "ai_quant" / ".ai_quant" / "job_runs")


def list_job_runs(domain: str | None, limit: int) -> list[dict[str, Any]]:
    n = max(1, min(limit, 200))
    return _list_runs_from_dir(get_job_store_dir(), domain, n)


def write_job_run(domain: str, payload: dict[str, Any]) -> dict[str, Any]:
    root = Path(get_job_store_dir())
    root.mkdir(parents=True, exist_ok=True)

    run_id = str(payload.get("runId") or "").strip() or uuid4().hex
    started_at = str(payload.get("startedAt") or "").strip() or datetime.now().isoformat(timespec="seconds")
    status = str(payload.get("status") or "running").strip()
    raw_message = payload.get("message")
    user_message = None
    if isinstance(raw_message, str):
        s = raw_message.strip()
        if s:
            one = s.splitlines()[0].strip()
            if len(one) > 200:
                one = one[:200]
            user_message = one

    record: dict[str, Any] = {
        "runId": run_id,
        "domain": domain,
        "startedAt": started_at,
        "finishedAt": payload.get("finishedAt"),
        "status": status,
        "dataSourceFinal": payload.get("dataSourceFinal") or "unknown",
        "fallbackChain": payload.get("fallbackChain") if isinstance(payload.get("fallbackChain"), list) else [],
        "rowsWritten": int(payload.get("rowsWritten") or 0),
        "itemsProcessed": int(payload.get("itemsProcessed") or 0),
        "failedItems": payload.get("failedItems") if isinstance(payload.get("failedItems"), list) else [],
        "message": raw_message,
        "userMessage": user_message,
    }

    tmp = root / f".{run_id}.json.tmp"
    out = root / f"{run_id}.json"
    tmp.write_text(json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(out)
    return record


def _list_runs_from_dir(dir_path: str, domain: str | None, limit: int) -> list[dict[str, Any]]:
    root = Path(dir_path)
    if not root.exists() or not root.is_dir():
        return []
    items: list[tuple[float, dict[str, Any]]] = []
    for p in root.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if domain and str(data.get("domain") or "") != domain:
            continue
        try:
            mtime = p.stat().st_mtime
        except Exception:
            mtime = 0.0
        items.append((mtime, data if isinstance(data, dict) else {}))
    items.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in items[:limit]]


def get_summary() -> dict[str, dict[str, Any]]:
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return _empty_summary()

    try:
        return _query_summary(conn, query_dict)
    except Exception:
        return _empty_summary()
    finally:
        conn.close()


def get_watchlist() -> dict[str, Any]:
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"items": [], "max": 50}
    try:
        rows = query_dict_func(
            conn,
            """
            SELECT w.stock_code, w.pinned, w.sort_order, m.stock_name
            FROM trade_watchlist w
            LEFT JOIN trade_stock_master m ON m.stock_code=w.stock_code
            ORDER BY w.pinned DESC, w.sort_order ASC, w.updated_at DESC
            """,
        )
        items = [
            {
                "stock_code": r.get("stock_code"),
                "stock_name": r.get("stock_name"),
                "pinned": bool(int(r.get("pinned") or 0) == 1),
                "sortOrder": int(r.get("sort_order") or 0),
            }
            for r in rows
        ]
        return {"items": items, "max": 50}
    except Exception:
        return {"items": [], "max": 50}
    finally:
        conn.close()


def _normalize_stock_code(code: str) -> str:
    return str(code or "").strip().upper()


def _stock_exists(conn: Any, query_dict_func: Any, code: str) -> bool:
    c = _normalize_stock_code(code)
    if not c:
        return False
    rows = query_dict_func(conn, "SELECT 1 AS x FROM trade_stock_master WHERE stock_code=%s LIMIT 1", (c,))
    if rows:
        return True
    rows2 = query_dict_func(conn, "SELECT 1 AS x FROM trade_stock_daily WHERE stock_code=%s LIMIT 1", (c,))
    return bool(rows2)


def add_watchlist_item(stock_code: str) -> dict[str, Any]:
    code = _normalize_stock_code(stock_code)
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"ok": False, "message": "数据库未配置或不可用"}
    try:
        if not _stock_exists(conn, query_dict_func, code):
            return {"ok": False, "message": "股票不存在"}
        next_order = query_dict_func(conn, "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM trade_watchlist")
        sort_order = int((next_order or [{}])[0].get("n") or 1)
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO trade_watchlist(stock_code, pinned, sort_order, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                  updated_at=NOW()
                """,
                (code, 0, sort_order),
            )
            try:
                conn.commit()
            except Exception:
                pass
            return {"ok": True}
        finally:
            try:
                cur.close()
            except Exception:
                pass
    finally:
        conn.close()


def delete_watchlist_item(stock_code: str) -> dict[str, Any]:
    code = _normalize_stock_code(stock_code)
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"ok": False, "message": "数据库未配置或不可用"}
    try:
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM trade_watchlist WHERE stock_code=%s", (code,))
            try:
                conn.commit()
            except Exception:
                pass
            return {"ok": True}
        finally:
            try:
                cur.close()
            except Exception:
                pass
    finally:
        conn.close()


def pin_watchlist_item(stock_code: str, pinned: bool) -> dict[str, Any]:
    code = _normalize_stock_code(stock_code)
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"ok": False, "message": "数据库未配置或不可用"}
    try:
        cur = conn.cursor()
        try:
            cur.execute("UPDATE trade_watchlist SET pinned=%s, updated_at=NOW() WHERE stock_code=%s", (1 if pinned else 0, code))
            try:
                conn.commit()
            except Exception:
                pass
            return {"ok": True}
        finally:
            try:
                cur.close()
            except Exception:
                pass
    finally:
        conn.close()


def reorder_watchlist(codes: list[str]) -> dict[str, Any]:
    ordered = []
    seen: set[str] = set()
    for c in codes or []:
        code = _normalize_stock_code(str(c or ""))
        if not code or code in seen:
            continue
        seen.add(code)
        ordered.append(code)
    if not ordered:
        return {"ok": False, "message": "codes 不能为空"}

    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"ok": False, "message": "数据库未配置或不可用"}
    try:
        cur = conn.cursor()
        try:
            vals = [(i + 1, code) for i, code in enumerate(ordered)]
            cur.executemany("UPDATE trade_watchlist SET sort_order=%s, updated_at=NOW() WHERE stock_code=%s", vals)
            try:
                conn.commit()
            except Exception:
                pass
            return {"ok": True}
        finally:
            try:
                cur.close()
            except Exception:
                pass
    finally:
        conn.close()


def search_stocks(q: str, limit: int) -> dict[str, Any]:
    text = q.strip()
    n = max(1, min(limit, 50))
    if not text:
        return {"items": []}
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"items": []}
    try:
        upper = text.upper()
        is_code_like = any(ch.isdigit() for ch in upper) or "." in upper
        code_like = f"{upper}%" if is_code_like else f"%{text}%"
        name_like = f"%{text}%"
        rows_master = query_dict_func(
            conn,
            """
            SELECT stock_code AS code, stock_name AS name
            FROM trade_stock_master
            WHERE stock_code LIKE %s OR stock_name LIKE %s
            ORDER BY stock_code
            LIMIT %s
            """,
            (code_like, name_like, n),
        )
        rows_daily = query_dict_func(
            conn,
            """
            SELECT stock_code AS code, MAX(stock_name) AS name
            FROM trade_stock_daily
            WHERE (stock_code LIKE %s OR stock_name LIKE %s)
              AND stock_name IS NOT NULL
              AND stock_name <> ''
            GROUP BY stock_code
            ORDER BY stock_code
            LIMIT %s
            """,
            (code_like, name_like, n),
        )

        daily_name_by_code: dict[str, str] = {}
        daily_ordered: list[dict[str, Any]] = []
        for r in rows_daily or []:
            code = str(r.get("code") or "").strip()
            if not code:
                continue
            name = str(r.get("name") or "").strip()
            if code not in daily_name_by_code:
                daily_ordered.append({"code": code, "name": name or None})
            if name:
                daily_name_by_code[code] = name

        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in rows_master or []:
            code = str(r.get("code") or "").strip()
            if not code or code in seen:
                continue
            name = str(r.get("name") or "").strip()
            if not name:
                name = daily_name_by_code.get(code, "")
            out.append({"code": code, "name": name or None})
            seen.add(code)
            if len(out) >= n:
                return {"items": out}

        for r in daily_ordered:
            code = str(r.get("code") or "").strip()
            if not code or code in seen:
                continue
            out.append({"code": code, "name": r.get("name")})
            seen.add(code)
            if len(out) >= n:
                break

        return {"items": out}
    except Exception:
        return {"items": []}
    finally:
        conn.close()


def _sina_suggest(keyword: str, limit: int) -> list[dict[str, str]]:
    k = str(keyword or "").strip()
    n = max(1, min(int(limit or 0), 50))
    if not k:
        return []

    url = (
        "http://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key="
        + urllib.parse.quote(k)
        + "&name=suggestdata"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = b""
    with urllib.request.urlopen(req, timeout=1.5) as resp:
        raw = resp.read() or b""

    try:
        text = raw.decode("gbk", errors="ignore")
    except Exception:
        text = raw.decode("utf-8", errors="ignore")

    m = re.search(r"\"(.*)\"", text)
    payload = (m.group(1) if m else "").strip()
    if not payload:
        return []

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for part in payload.split(";"):
        fields = [x.strip() for x in (part or "").split(",")]
        if len(fields) < 5:
            continue
        market = fields[3] or fields[0]
        code6 = fields[2] or (market[-6:] if len(market) >= 6 else "")
        name = fields[4] or ""
        if not code6 or len(code6) != 6:
            continue
        full = None
        if str(market).startswith("sh"):
            full = f"{code6}.SH"
        elif str(market).startswith("sz"):
            full = f"{code6}.SZ"
        if not full or full in seen:
            continue
        seen.add(full)
        out.append({"code": full, "name": name})
        if len(out) >= n:
            break
    return out


def _upsert_stock_master(conn: Any, items: list[dict[str, str]]) -> None:
    vals: list[tuple[str, str, str]] = []
    for it in items:
        code = str(it.get("code") or "").strip()
        name = str(it.get("name") or "").strip()
        if not code:
            continue
        vals.append((code, name, "sina"))
    if not vals:
        return
    cur = conn.cursor()
    try:
        cur.executemany(
            """
            INSERT INTO trade_stock_master(stock_code, stock_name, source, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
              stock_name=VALUES(stock_name),
              source=VALUES(source),
              updated_at=VALUES(updated_at)
            """,
            vals,
        )
        try:
            conn.commit()
        except Exception:
            pass
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _get_conn_and_query() -> tuple[Any, Any]:
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return None, None
    return conn, query_dict


def _query_summary(conn: Any, query_dict_func: Any) -> dict[str, dict[str, Any]]:
    def safe(sql: str) -> list[dict[str, Any]]:
        try:
            return query_dict_func(conn, sql)
        except Exception:
            return [{"d": None, "c": 0}]

    daily = safe("SELECT MAX(trade_date) AS d, COUNT(*) AS c FROM trade_stock_daily")
    fin = safe("SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_stock_financial")
    news = safe("SELECT MAX(published_at) AS d, COUNT(*) AS c FROM trade_stock_news")
    macro = safe("SELECT MAX(indicator_date) AS d, COUNT(*) AS c FROM trade_macro_indicator")
    rate = safe("SELECT MAX(rate_date) AS d, COUNT(*) AS c FROM trade_rate_daily")
    report = safe("SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_report_consensus")
    cal = safe("SELECT MAX(event_date) AS d, COUNT(*) AS c FROM trade_calendar_event")

    def pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
        row = (rows or [{}])[0]
        return {"latest": row.get("d"), "count": int(row.get("c") or 0)}

    return {
        "trade_stock_daily": pack(daily),
        "trade_stock_financial": pack(fin),
        "trade_stock_news": pack(news),
        "trade_macro_indicator": pack(macro),
        "trade_rate_daily": pack(rate),
        "trade_report_consensus": pack(report),
        "trade_calendar_event": pack(cal),
    }


def _empty_summary() -> dict[str, dict[str, Any]]:
    return {
        "trade_stock_daily": {"latest": None, "count": 0},
        "trade_stock_financial": {"latest": None, "count": 0},
        "trade_stock_news": {"latest": None, "count": 0},
        "trade_macro_indicator": {"latest": None, "count": 0},
        "trade_rate_daily": {"latest": None, "count": 0},
        "trade_report_consensus": {"latest": None, "count": 0},
        "trade_calendar_event": {"latest": None, "count": 0},
    }
