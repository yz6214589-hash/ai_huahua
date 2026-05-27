"""
Charles 服务模块 - 股票数据与任务管理服务

本模块提供以下核心功能：
- 任务运行记录管理（Job Run Tracking）：跟踪和管理AI量化任务的执行状态
- 自选股管理：用户自选股票的添加、删除、置顶和排序
- 股票搜索：支持按股票代码或名称搜索股票
- 数据库摘要统计：获取各数据表的最新更新时间和记录数量
- 新浪股票API集成：获取实时股票建议

所有数据默认存储在项目根目录的 .ai_quant/job_runs 文件夹下，
可通过环境变量 AI_QUANT_CHARLES_JOB_STORE_DIR 自定义路径。
"""

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

from core.db import connect, load_mysql_config, query_dict


def _project_root() -> Path:
    """获取项目根目录的路径"""
    return Path(__file__).resolve().parents[3]


def _default_job_store_dir() -> str:
    return str(_project_root() / ".ai_quant" / "job_runs")


def get_job_store_dir() -> str:
    """
    获取任务运行记录的存储目录路径
    
    优先使用环境变量 AI_QUANT_CHARLES_JOB_STORE_DIR，
    如果未设置则使用项目根目录下的默认路径。
    
    Returns:
        str: 任务运行记录存储目录的绝对路径
    """
    env = os.getenv("AI_QUANT_CHARLES_JOB_STORE_DIR", "").strip()
    if env:
        try:
            p = Path(env)
            p.mkdir(parents=True, exist_ok=True)
            t = p / ".perm_check.tmp"
            t.write_text("ok", encoding="utf-8")
            t.unlink(missing_ok=True)
            return str(p)
        except Exception:
            pass
    return _default_job_store_dir()


def list_job_runs(domain: str | None, limit: int) -> list[dict[str, Any]]:
    """
    获取任务运行记录列表
    
    Args:
        domain: 可选的领域/业务线过滤条件，为None时返回所有记录
        limit: 返回记录数量的上限，最大不超过200
    
    Returns:
        list[dict[str, Any]]: 任务运行记录列表，按修改时间倒序排列
    """
    n = max(1, min(limit, 200))
    return _list_runs_from_dir(get_job_store_dir(), domain, n)


def read_job_run(run_id: str) -> dict[str, Any] | None:
    rid = str(run_id or "").strip()
    if not rid:
        return None
    for base in [get_job_store_dir(), _default_job_store_dir()]:
        try:
            p = Path(base) / f"{rid}.json"
            if p.exists() and p.is_file():
                obj = json.loads(p.read_text(encoding="utf-8"))
                return obj if isinstance(obj, dict) else None
        except Exception:
            continue
    return None


def write_job_run(domain: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    写入任务运行记录
    
    将任务执行状态和结果写入JSON文件存储。
    使用原子写入（先写临时文件再重命名）确保数据一致性。
    
    Args:
        domain: 任务所属的领域/业务线标识
        payload: 任务运行数据，包含runId、startedAt、status等字段
    
    Returns:
        dict[str, Any]: 写入的完整记录数据
    """
    root = Path(get_job_store_dir())
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception:
        root = Path(_default_job_store_dir())
        root.mkdir(parents=True, exist_ok=True)

    # 生成或使用传入的运行ID
    run_id = str(payload.get("runId") or "").strip() or uuid4().hex
    # 使用传入的开始时间或当前时间
    started_at = str(payload.get("startedAt") or "").strip() or datetime.now().isoformat(timespec="seconds")
    # 默认状态为running（运行中）
    status = str(payload.get("status") or "running").strip()
    raw_message = payload.get("message")
    # 提取用户友好的消息（取第一行，最多200字符）
    user_message = None
    if isinstance(raw_message, str):
        s = raw_message.strip()
        if s:
            one = s.splitlines()[0].strip()
            if len(one) > 200:
                one = one[:200]
            user_message = one

    # 构建完整的记录数据
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

    # 原子写入：先写临时文件，再重命名
    tmp = root / f".{run_id}.json.tmp"
    out = root / f"{run_id}.json"
    try:
        tmp.write_text(json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(out)
    except Exception:
        root2 = Path(_default_job_store_dir())
        root2.mkdir(parents=True, exist_ok=True)
        tmp2 = root2 / f".{run_id}.json.tmp"
        out2 = root2 / f"{run_id}.json"
        tmp2.write_text(json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8")
        tmp2.replace(out2)
    return record


def _list_runs_from_dir(dir_path: str, domain: str | None, limit: int) -> list[dict[str, Any]]:
    """
    从指定目录读取任务运行记录
    
    内部函数，遍历目录下的所有JSON文件并按修改时间排序。
    
    Args:
        dir_path: JSON文件所在的目录路径
        domain: 可选的领域过滤条件
        limit: 返回记录数量的上限
    
    Returns:
        list[dict[str, Any]]: 任务运行记录列表
    """
    root = Path(dir_path)
    # 目录不存在或不是目录则返回空列表
    if not root.exists() or not root.is_dir():
        return []
    items: list[tuple[float, dict[str, Any]]] = []
    # 遍历所有JSON文件
    for p in root.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        # 按领域过滤
        if domain and str(data.get("domain") or "") != domain:
            continue
        try:
            mtime = p.stat().st_mtime
        except Exception:
            mtime = 0.0
        items.append((mtime, data if isinstance(data, dict) else {}))
    # 按修改时间倒序排列（最新的在前）
    items.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in items[:limit]]


def get_summary() -> dict[str, dict[str, Any]]:
    """
    获取数据库摘要统计信息
    
    查询各数据表的最新更新时间和记录数量，
    包括股票日线、财务数据、新闻、宏观指标等。
    
    Returns:
        dict[str, dict[str, Any]]: 各表的统计信息，键为表名，值为包含latest和count的字典
    """
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
    """
    获取用户自选股列表
    
    从数据库查询用户的自选股票列表，
    按置顶状态、排序顺序和更新时间排序。
    
    Returns:
        dict[str, Any]: 包含items（自选股列表）和max（最大数量50）的字典
    """
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"items": [], "max": 50}
    try:
        # 查询自选股及其关联的股票信息
        rows = query_dict_func(
            conn,
            """
            SELECT w.stock_code, w.pinned, w.sort_order, m.stock_name
            FROM trade_watchlist w
            LEFT JOIN trade_stock_master m ON m.stock_code=w.stock_code
            ORDER BY w.pinned DESC, w.sort_order ASC, w.updated_at DESC
            """,
        )
        # 转换为响应格式
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
    """
    标准化股票代码
    
    去除空格并转换为大写。
    
    Args:
        code: 原始股票代码
    
    Returns:
        str: 标准化后的股票代码
    """
    return str(code or "").strip().upper()


def _stock_exists(conn: Any, query_dict_func: Any, code: str) -> bool:
    """
    检查股票是否存在
    
    在trade_stock_master和trade_stock_daily表中查询股票代码。
    
    Args:
        conn: 数据库连接对象
        query_dict_func: 查询函数
        code: 股票代码
    
    Returns:
        bool: 股票是否存在
    """
    c = _normalize_stock_code(code)
    if not c:
        return False
    # 先查主表
    rows = query_dict_func(conn, "SELECT 1 AS x FROM trade_stock_master WHERE stock_code=%s LIMIT 1", (c,))
    if rows:
        return True
    # 再查日线表
    rows2 = query_dict_func(conn, "SELECT 1 AS x FROM trade_stock_daily WHERE stock_code=%s LIMIT 1", (c,))
    return bool(rows2)


def add_watchlist_item(stock_code: str) -> dict[str, Any]:
    """
    添加股票到自选股列表
    
    Args:
        stock_code: 股票代码
    
    Returns:
        dict[str, Any]: 操作结果，包含ok（是否成功）和message（消息）
    """
    code = _normalize_stock_code(stock_code)
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"ok": False, "message": "数据库未配置或不可用"}
    try:
        # 检查股票是否存在
        if not _stock_exists(conn, query_dict_func, code):
            return {"ok": False, "message": "股票不存在"}
        # 获取下一个排序序号
        next_order = query_dict_func(conn, "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM trade_watchlist")
        sort_order = int((next_order or [{}])[0].get("n") or 1)
        cur = conn.cursor()
        try:
            # 插入新记录，已存在则只更新时间
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
    """
    从自选股列表中删除股票
    
    Args:
        stock_code: 股票代码
    
    Returns:
        dict[str, Any]: 操作结果
    """
    code = _normalize_stock_code(stock_code)
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"ok": False, "message": "数据库未配置或不可用"}
    try:
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM trade_watchlist_item_group WHERE stock_code=%s", (code,))
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
    """
    设置自选股的置顶状态
    
    Args:
        stock_code: 股票代码
        pinned: 是否置顶（True为置顶，False为取消置顶）
    
    Returns:
        dict[str, Any]: 操作结果
    """
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
    """
    重新排序自选股列表
    
    根据传入的股票代码顺序更新数据库中的排序序号。
    
    Args:
        codes: 股票代码列表，表示新的排序顺序
    
    Returns:
        dict[str, Any]: 操作结果
    """
    ordered = []
    seen: set[str] = set()
    # 去重并标准化股票代码
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
            # 批量更新排序序号
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


_master_backfill_done: bool = False


def _ensure_stock_master_complete() -> None:
    global _master_backfill_done
    if _master_backfill_done:
        return
    _master_backfill_done = True
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return
    def _fetch_sina_name(code):
        k = code.strip().upper()
        if k.endswith(".SH") or k.endswith(".SZ") or k.endswith(".BJ"):
            k = k.rsplit(".", 1)[0]
        if not k:
            return None
        try:
            url = ("http://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key=" + urllib.parse.quote(k) + "&name=suggestdata")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                raw = resp.read() or b""
            try:
                t = raw.decode("gbk", errors="ignore")
            except Exception:
                t = raw.decode("utf-8", errors="ignore")
            m2 = re.search(r'\"(.*)\"', t)
            payload = (m2.group(1) if m2 else "").strip()
            if not payload:
                return None
            for part in payload.split(";"):
                fields = [x.strip() for x in (part or "").split(",")]
                if len(fields) < 5:
                    continue
                code6 = fields[2] or ""
                name = fields[4] or ""
                if code6.upper() == k and name:
                    return name
            return None
        except Exception:
            return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM trade_stock_master")
        master_count = cur.fetchone()["cnt"]
        if master_count >= 5000:
            cur.close()
            return
        cur.execute("SELECT stock_code AS code FROM trade_stock_daily WHERE stock_code IS NOT NULL AND stock_code <> '' GROUP BY stock_code")
        all_codes = [str(r.get("code") or "").strip() for r in cur.fetchall() if r.get("code")]
        if not all_codes:
            cur.close()
            return
        cur.execute("SELECT stock_code AS code FROM trade_stock_master")
        existing = {str(r.get("code") or "").strip() for r in cur.fetchall()}
        missing = [c for c in all_codes if c not in existing]
        if not missing:
            cur.close()
            return
        for i in range(0, min(len(missing), 200), 50):
            batch = missing[i:i+50]
            vals = [(c, _fetch_sina_name(c), "sina") for c in batch if _fetch_sina_name(c)]
            if vals:
                try:
                    cur.executemany("INSERT INTO trade_stock_master(stock_code, stock_name, source, updated_at) VALUES (%s, %s, %s, NOW()) ON DUPLICATE KEY UPDATE stock_name=VALUES(stock_name), source=VALUES(source), updated_at=VALUES(updated_at)", vals)
                    conn.commit()
                except Exception:
                    pass
        cur.close()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass





def search_stocks(q: str, limit: int, offset: int = 0) -> dict[str, Any]:
    """
    搜索股票

    仅从 trade_stock_master 表查询股票。
    首次调用时自动回填缺失的股票数据。

    Args:
        q: 搜索关键词
        limit: 返回结果数量上限
        offset: 结果偏移量，用于分页加载

    Returns:
        dict[str, Any]: 包含items（股票列表）的字典
    """
    _ensure_stock_master_complete()

    text = q.strip()
    n = max(1, limit)
    o = max(0, offset)
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"items": []}
    try:
        if not text:
            rows = query_dict_func(
                conn,
                "SELECT stock_code AS code, stock_name AS name FROM trade_stock_master ORDER BY stock_code LIMIT %s OFFSET %s",
                (n, o),
            )
            return {"items": [{"code": str(r["code"]), "name": str(r["name"]) if r["name"] else None} for r in (rows or [])]}

        upper = text.upper()
        is_code_like = any(ch.isdigit() for ch in upper) or "." in upper
        code_like = f"{upper}%" if is_code_like else f"%{text}%"
        name_like = f"%{text}%"

        rows = query_dict_func(
            conn,
            """
            SELECT stock_code AS code, stock_name AS name
            FROM trade_stock_master
            WHERE stock_code LIKE %s OR stock_name LIKE %s
            ORDER BY stock_code
            LIMIT %s OFFSET %s
            """,
            (code_like, name_like, n, o),
        )

        out = []
        seen = set()
        for r in rows or []:
            code = str(r.get("code") or "").strip()
            if not code or code in seen:
                continue
            name = str(r.get("name") or "").strip()
            out.append({"code": code, "name": name or None})
            seen.add(code)
            if len(out) >= n:
                break

        return {"items": out}
    except Exception:
        return {"items": []}
    finally:
        conn.close()



def _sina_suggest(keyword: str, limit: int) -> list[dict[str, str]]:
    """
    从新浪股票API获取股票建议
    
    调用新浪股票搜索接口，返回匹配的股票列表。
    
    Args:
        keyword: 搜索关键词
        limit: 返回结果数量上限（最大50）
    
    Returns:
        list[dict[str, str]]: 股票列表，每项包含code和name
    """
    k = str(keyword or "").strip()
    n = max(1, min(int(limit or 0), 50))
    if not k:
        return []

    # 构建新浪股票搜索URL
    url = (
        "http://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key="
        + urllib.parse.quote(k)
        + "&name=suggestdata"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = b""
    with urllib.request.urlopen(req, timeout=1.5) as resp:
        raw = resp.read() or b""

    # 新浪API返回GBK编码
    try:
        text = raw.decode("gbk", errors="ignore")
    except Exception:
        text = raw.decode("utf-8", errors="ignore")

    # 提取JSONP数据部分
    m = re.search(r"\"(.*)\"", text)
    payload = (m.group(1) if m else "").strip()
    if not payload:
        return []

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    # 解析返回结果，每条记录以分号分隔
    for part in payload.split(";"):
        fields = [x.strip() for x in (part or "").split(",")]
        if len(fields) < 5:
            continue
        # 提取市场代码和股票代码
        market = fields[3] or fields[0]
        code6 = fields[2] or (market[-6:] if len(market) >= 6 else "")
        name = fields[4] or ""
        if not code6 or len(code6) != 6:
            continue
        # 转换为标准股票代码格式（6位代码.SH或.SZ）
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
    """
    批量插入或更新股票主表数据
    
    如果股票代码已存在则更新名称，否则插入新记录。
    
    Args:
        conn: 数据库连接对象
        items: 股票数据列表，每项包含code和name
    """
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
        # 使用ON DUPLICATE KEY UPDATE实现插入或更新
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
    """
    获取数据库连接和查询函数
    
    Returns:
        tuple[Any, Any]: (连接对象, 查询函数) 或 (None, None)
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return None, None
    return conn, query_dict


def _query_summary(conn: Any, query_dict_func: Any) -> dict[str, dict[str, Any]]:
    """
    查询数据库各表的统计信息
    
    Args:
        conn: 数据库连接对象
        query_dict_func: 查询函数
    
    Returns:
        dict[str, dict[str, Any]]: 各表的统计信息
    """
    def safe(sql: str) -> list[dict[str, Any]]:
        """安全执行查询，失败时返回默认值"""
        try:
            return query_dict_func(conn, sql)
        except Exception:
            return [{"d": None, "c": 0}]

    # 查询各表的最新日期和记录数量
    daily = safe("SELECT MAX(trade_date) AS d, COUNT(*) AS c FROM trade_stock_daily")
    fin = safe("SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_stock_financial")
    news = safe("SELECT MAX(published_at) AS d, COUNT(*) AS c FROM trade_stock_news")
    macro = safe("SELECT MAX(indicator_date) AS d, COUNT(*) AS c FROM trade_macro_indicator")
    rate = safe("SELECT MAX(rate_date) AS d, COUNT(*) AS c FROM trade_rate_daily")
    report = safe("SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_report_consensus")
    cal = safe("SELECT MAX(event_date) AS d, COUNT(*) AS c FROM trade_calendar_event")

    def pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
        """将查询结果打包为统一格式"""
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
    """
    返回空的统计摘要
    
    数据库连接失败时返回此默认值。
    
    Returns:
        dict[str, dict[str, Any]]: 所有表的统计值均为空
    """
    return {
        "trade_stock_daily": {"latest": None, "count": 0},
        "trade_stock_financial": {"latest": None, "count": 0},
        "trade_stock_news": {"latest": None, "count": 0},
        "trade_macro_indicator": {"latest": None, "count": 0},
        "trade_rate_daily": {"latest": None, "count": 0},
        "trade_report_consensus": {"latest": None, "count": 0},
        "trade_calendar_event": {"latest": None, "count": 0},
    }


def get_watchlist_snapshots() -> dict[str, Any]:
    """
    获取自选股行情快照
    对于每只自选股，取最新2条日K线，计算最新价、涨跌额、涨跌幅
    MySQL 5.7 兼容版本，使用子查询替代窗口函数
    """
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"items": []}
    try:
        watchlist = query_dict_func(conn, "SELECT stock_code FROM trade_watchlist", ())
        if not watchlist:
            return {"items": []}
        codes = [r["stock_code"] for r in watchlist]
        if not codes:
            return {"items": []}
        
        items = []
        for r in watchlist:
            code = r["stock_code"]
            try:
                latest_rows = query_dict_func(
                    conn,
                    "SELECT trade_date, close_price FROM trade_stock_daily WHERE stock_code=%s ORDER BY trade_date DESC LIMIT 2",
                    (code,)
                )
                if not latest_rows:
                    items.append({
                        "stock_code": code,
                        "stock_name": None,
                        "price": None,
                        "change": None,
                        "pctChange": None,
                        "trade_date": None,
                        "source": "daily",
                    })
                    continue
                
                latest = latest_rows[0]
                prev = latest_rows[1] if len(latest_rows) > 1 else None
                close = latest.get("close_price")
                prev_close = prev.get("close_price") if prev else None
                change = round(float(close - prev_close), 2) if close is not None and prev_close is not None else None
                pct = round(float((close - prev_close) / prev_close * 100), 2) if close is not None and prev_close is not None and prev_close != 0 else None
                
                items.append({
                    "stock_code": code,
                    "stock_name": latest.get("stock_name"),
                    "price": float(close) if close is not None else None,
                    "change": change,
                    "pctChange": pct,
                    "trade_date": str(latest.get("trade_date")) if latest.get("trade_date") else None,
                    "source": "daily",
                })
            except Exception:
                items.append({
                    "stock_code": code,
                    "stock_name": None,
                    "price": None,
                    "change": None,
                    "pctChange": None,
                    "trade_date": None,
                    "source": "daily",
                })
        return {"items": items}
    finally:
        conn.close()


def get_watchlist_groups() -> dict[str, Any]:
    """获取所有自定义分组（含股票数量）"""
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"items": []}
    try:
        rows = query_dict_func(conn,
            """SELECT g.id, g.name, g.sort_order,
                      COUNT(w.stock_code) AS stock_count
               FROM trade_watchlist_group g
               LEFT JOIN trade_watchlist_item_group wig ON g.id = wig.group_id
               LEFT JOIN trade_watchlist w ON wig.stock_code = w.stock_code
               GROUP BY g.id
               ORDER BY g.sort_order, g.id""", ())
        return {"items": [{
            "id": r["id"],
            "name": r["name"],
            "sort_order": r["sort_order"],
            "stock_count": int(r["stock_count"] or 0),
        } for r in (rows or [])]}
    finally:
        conn.close()


def create_watchlist_group(name: str) -> dict[str, Any]:
    """新建分组"""
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"error": "数据库连接失败"}
    try:
        cur = conn.cursor()
        # 检查分组名是否已存在
        cur.execute("SELECT id FROM trade_watchlist_group WHERE name=%s", (name,))
        if cur.fetchone():
            cur.close()
            return {"error": f"分组名称「{name}」已存在"}
        cur.execute("SELECT MAX(sort_order) AS m FROM trade_watchlist_group", ())
        row = cur.fetchone()
        next_order = (row["m"] or 0) + 1
        cur.execute("INSERT INTO trade_watchlist_group (name, sort_order) VALUES (%s, %s)", (name, next_order))
        gid = cur.lastrowid
        conn.commit()
        cur.close()
        return {"id": gid, "name": name, "sort_order": next_order}
    finally:
        conn.close()


def rename_watchlist_group(group_id: int, name: str) -> dict[str, Any]:
    """重命名分组"""
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"error": "数据库连接失败"}
    try:
        cur = conn.cursor()
        # 检查其他分组是否已使用该名称
        cur.execute("SELECT id FROM trade_watchlist_group WHERE name=%s AND id!=%s", (name, group_id))
        if cur.fetchone():
            cur.close()
            return {"error": f"分组名称「{name}」已存在"}
        cur.execute("UPDATE trade_watchlist_group SET name=%s WHERE id=%s", (name, group_id))
        conn.commit()
        cur.close()
        return {"ok": True}
    finally:
        conn.close()


def delete_watchlist_group(group_id: int) -> dict[str, Any]:
    """删除分组（级联删除关系）"""
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"error": "数据库连接失败"}
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM trade_watchlist_group WHERE id=%s", (group_id,))
        conn.commit()
        cur.close()
        return {"ok": True}
    finally:
        conn.close()


def add_watchlist_item_with_groups(stock_code: str, group_ids: list[int]) -> dict[str, Any]:
    """添加自选股，同时写入分组关系"""
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"error": "数据库连接失败"}
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM trade_watchlist WHERE stock_code=%s", (stock_code,))
        existing = cur.fetchone()
        if not existing:
            cur.execute("INSERT INTO trade_watchlist (stock_code) VALUES (%s)", (stock_code,))
        if group_ids:
            for gid in group_ids:
                cur.execute(
                    "INSERT IGNORE INTO trade_watchlist_item_group (stock_code, group_id) VALUES (%s, %s)",
                    (stock_code, gid)
                )
        conn.commit()
        cur.close()
        return {"ok": True}
    finally:
        conn.close()


def get_watchlist_by_group(group_id: int | None) -> dict[str, Any]:
    """
    按分组查询自选股
    group_id=None 返回全部（不过滤）
    """
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"items": []}
    try:
        if group_id is None:
            rows = query_dict_func(conn,
                """SELECT w.stock_code, m.stock_name, w.pinned, w.sort_order,
                          GROUP_CONCAT(wig.group_id) AS group_ids
                   FROM trade_watchlist w
                   LEFT JOIN trade_stock_master m ON w.stock_code = m.stock_code
                   LEFT JOIN trade_watchlist_item_group wig ON w.stock_code = wig.stock_code
                   GROUP BY w.stock_code
                   ORDER BY w.pinned DESC, w.sort_order DESC""", ())
        else:
            rows = query_dict_func(conn,
                """SELECT w.stock_code, m.stock_name, w.pinned, w.sort_order,
                          GROUP_CONCAT(wig.g) AS group_ids
                   FROM trade_watchlist w
                   JOIN (
                       SELECT stock_code, group_id AS g FROM trade_watchlist_item_group WHERE group_id=%s
                   ) wig ON w.stock_code = wig.stock_code
                   LEFT JOIN trade_stock_master m ON w.stock_code = m.stock_code
                   GROUP BY w.stock_code
                   ORDER BY w.pinned DESC, w.sort_order""", (group_id,))
        items = []
        for r in (rows or []):
            gids = [int(x) for x in r["group_ids"].split(",") if r["group_ids"]] if r["group_ids"] else []
            items.append({
                "stock_code": r["stock_code"],
                "stock_name": r.get("stock_name"),
                "pinned": bool(r["pinned"]),
                "sort_order": r["sort_order"],
                "group_ids": gids,
            })
        return {"items": items}
    finally:
        conn.close()

