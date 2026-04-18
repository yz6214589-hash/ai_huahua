from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any

import yaml
from openai import OpenAI

from ..db import MySQLConfig, connect, executemany, query_dict
from ..models import DataSource
from .common import JobStats


INSERT_SQL = """
INSERT INTO trade_calendar_event
(event_date, event_time, title, country, category, importance, source, ai_prompt)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
importance = GREATEST(importance, VALUES(importance)),
category = VALUES(category),
source = VALUES(source),
ai_prompt = COALESCE(VALUES(ai_prompt), ai_prompt)
"""


def _parse_json_array(content: str) -> list[dict[str, Any]]:
    start = content.find("[")
    end = content.rfind("]")
    if start == -1 or end == -1:
        return []
    return list(json.loads(content[start : end + 1]))


def _call_qwen(client: OpenAI, prompt: str, enable_search: bool = False) -> str:
    extra = {}
    if enable_search:
        extra = {"enable_search": True, "search_options": {"forced_search": True}}
    completion = client.chat.completions.create(
        model="qwen-max",
        messages=[{"role": "user", "content": prompt}],
        extra_body=extra,
    )
    return completion.choices[0].message.content.strip()


def run_catalyst(cfg: MySQLConfig, _mode: str | None, params: dict[str, Any] | None) -> JobStats:
    prompt_file = (params or {}).get("prompts_yaml")
    if not prompt_file:
        prompt_file = os.path.join(os.getcwd(), "week2", "课程代码-20260225", "CASE-数据采集", "prompts.yaml")

    dashscope_key = (params or {}).get("dashscope_api_key") or os.getenv("DASHSCOPE_API_KEY", "")
    if not dashscope_key:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final=DataSource.qwen_search,
            fallback_chain=[DataSource.qwen_search],
            message="缺少 DASHSCOPE_API_KEY，无法执行催化剂联网搜索",
        )

    with open(prompt_file, "r", encoding="utf-8") as f:
        cfg_yaml = yaml.safe_load(f)

    today = datetime.now().date()
    start_date = today.isoformat()
    end_date = (today + timedelta(days=180)).isoformat()
    prompt = str(cfg_yaml["calendar"]["search_catalysts"]).format(start_date=start_date, end_date=end_date)

    client = OpenAI(api_key=dashscope_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    content = _call_qwen(client, prompt, enable_search=True)
    events = _parse_json_array(content)
    if not events:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final=DataSource.qwen_search,
            fallback_chain=[DataSource.qwen_search],
            message="未解析到事件 JSON 数组",
        )

    prompt_tpl = str(cfg_yaml["calendar"]["generate_prompts"])
    events_brief = [{"date": e.get("date", ""), "title": e.get("title", ""), "country": e.get("country", "")} for e in events]
    prompts_map: dict[str, str] = {}
    for i in range(0, len(events_brief), 20):
        batch = events_brief[i : i + 20]
        p = prompt_tpl.format(events_json=json.dumps(batch, ensure_ascii=False, indent=2))
        res = _parse_json_array(_call_qwen(client, p, enable_search=False))
        for r in res:
            t = str(r.get("title", "")).strip()
            ap = str(r.get("prompt", "")).strip()
            if t and ap:
                prompts_map[t] = ap

    conn = connect(cfg)
    try:
        existing = query_dict(conn, "SELECT event_date, title FROM trade_calendar_event WHERE source='qwen_search'")
        existing_keys = {(r["event_date"].strftime("%Y-%m-%d"), str(r["title"])) for r in existing if r.get("event_date") and r.get("title")}

        rows = []
        for evt in events:
            date_str = str(evt.get("date", "")).strip()
            title = str(evt.get("title", "")).strip()
            if not date_str or not title:
                continue
            if (date_str, title) in existing_keys:
                continue
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                continue
            country = str(evt.get("country", "中国") or "中国")
            category = str(evt.get("category", "policy") or "policy")
            importance = int(evt.get("importance", 2) or 2)
            if importance < 2:
                importance = 2
            if importance > 3:
                importance = 3
            ai_prompt = prompts_map.get(title)
            rows.append((date_str, None, title, country, category, importance, "qwen_search", ai_prompt))

        written = executemany(conn, INSERT_SQL, rows)
        conn.commit()
        return JobStats(
            items_processed=len(rows),
            rows_written=written,
            failed_items=[],
            data_source_final=DataSource.qwen_search,
            fallback_chain=[DataSource.qwen_search],
            message=None,
        )
    finally:
        conn.close()

