from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from ..db import MySQLConfig, connect, execute, executemany, query_dict


def _normalize_stock_code(code: str) -> str:
    c = (code or "").strip().upper()
    if not c:
        return ""
    if "." in c:
        return c
    if len(c) == 6:
        return c
    return c


def _to_digits(code: str) -> str:
    c = _normalize_stock_code(code)
    if "." in c:
        return c.split(".", 1)[0]
    return c


def run_sentiment_run(mysql_cfg: MySQLConfig, run_id: str) -> None:
    conn = connect(mysql_cfg)
    try:
        rows = query_dict(conn, "SELECT * FROM trade_sentiment_run WHERE run_id=%s", (run_id,))
        if not rows:
            return
        r = rows[0]
        stock_codes = json.loads(str(r.get("stock_codes_json") or "[]"))
        stock_names = json.loads(str(r.get("stock_names_json") or "[]")) if r.get("stock_names_json") else []
        days = int(r.get("days") or 3)
        use_llm = int(r.get("use_llm") or 0) == 1
        execute(conn, "UPDATE trade_sentiment_run SET status=%s, started_at=NOW() WHERE run_id=%s", ("running", run_id))
        conn.commit()
    finally:
        conn.close()

    try:
        if use_llm and not (os.getenv("DASHSCOPE_API_KEY") or "").strip():
            raise RuntimeError("DASHSCOPE_API_KEY required")

        from .nanobot_event import detect_events
        from .nanobot_news import fetch_stock_news_and_notices
        from .nanobot_sentiment import score_one

        news_rows: list[tuple[Any, ...]] = []
        event_rows: list[tuple[Any, ...]] = []

        for i, code in enumerate(stock_codes if isinstance(stock_codes, list) else []):
            stock_code = _normalize_stock_code(str(code))
            stock_name = str(stock_names[i] if i < len(stock_names) else "").strip()
            digits = _to_digits(stock_code)
            items = fetch_stock_news_and_notices(digits, days=days, limit=50)
            for it in items:
                title = str(it.get("title") or "")[:255]
                content = str(it.get("content") or "")
                published_at = it.get("published_at")
                url = it.get("url")
                source_type = str(it.get("source_type") or "news")
                sentiment = None
                strength = None
                summary = None
                market_impact = None
                if use_llm:
                    scored = score_one(f"{title}\n{content}".strip())
                    sentiment = scored.get("sentiment")
                    strength = scored.get("strength")
                    summary = scored.get("summary")
                    market_impact = scored.get("market_impact")

                news_rows.append(
                    (
                        run_id,
                        stock_code,
                        stock_name,
                        source_type,
                        title,
                        url,
                        published_at,
                        content,
                        sentiment,
                        strength,
                        summary,
                        market_impact,
                    )
                )

                evs = detect_events({"title": title, "content": content}, use_llm=use_llm)
                for ev in evs:
                    event_rows.append(
                        (
                            run_id,
                            stock_code,
                            stock_name,
                            source_type,
                            title,
                            url,
                            published_at,
                            str(ev.get("event_type") or ""),
                            str(ev.get("event_category") or ""),
                            str(ev.get("signal") or ""),
                            ev.get("signal_reason"),
                            ev.get("impact"),
                            int(ev.get("confidence") or 3),
                            str(ev.get("urgency") or "中"),
                        )
                    )

        conn2 = connect(mysql_cfg)
        try:
            executemany(
                conn2,
                """
                INSERT INTO trade_sentiment_news
                  (run_id, stock_code, stock_name, source_type, title, url, published_at, content, sentiment, strength, summary, market_impact)
                VALUES
                  (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                news_rows,
            )
            executemany(
                conn2,
                """
                INSERT INTO trade_sentiment_event
                  (run_id, stock_code, stock_name, source_type, source_title, source_url, published_at,
                   event_type, event_category, signal_action, signal_reason, impact, confidence, urgency)
                VALUES
                  (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                event_rows,
            )
            execute(
                conn2,
                "UPDATE trade_sentiment_run SET status=%s, finished_at=NOW(), total_events=%s WHERE run_id=%s",
                ("success", int(len(event_rows)), run_id),
            )
            conn2.commit()
        finally:
            conn2.close()
    except Exception as e:
        conn3 = connect(mysql_cfg)
        try:
            execute(
                conn3,
                "UPDATE trade_sentiment_run SET status=%s, finished_at=NOW(), error_message=%s WHERE run_id=%s",
                ("failed", f"{type(e).__name__}: {e}", run_id),
            )
            conn3.commit()
        finally:
            conn3.close()
