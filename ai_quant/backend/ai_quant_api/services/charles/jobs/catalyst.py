from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any

from ai_quant_api.db import MySQLConfig, connect, executemany, query_dict

from .common import JobStats, to_ymd


_INSERT_SQL = """
INSERT INTO trade_calendar_event
(event_date, event_time, country, category, title, importance, previous_value, forecast_value, actual_value, impact, ai_prompt, source, source_url, status)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
category=COALESCE(VALUES(category), category),
importance=COALESCE(VALUES(importance), importance),
impact=COALESCE(VALUES(impact), impact),
ai_prompt=COALESCE(VALUES(ai_prompt), ai_prompt),
source=COALESCE(VALUES(source), source),
source_url=COALESCE(VALUES(source_url), source_url),
status=COALESCE(VALUES(status), status)
"""

def _country_code(v: str) -> str:
    s = (v or "").strip().upper()
    if not s:
        return "CN"
    if s in ("CN", "US", "EU", "JP"):
        return s
    if "中国" in s or "CHINA" in s:
        return "CN"
    if "美国" in s or "UNITED" in s or "USA" in s:
        return "US"
    if "欧" in s or "EURO" in s:
        return "EU"
    if "日" in s or "JAPAN" in s:
        return "JP"
    return "CN"


def _status_by_date(d: str) -> str:
    try:
        today = datetime.now().date()
        y, m, dd = [int(x) for x in d.split("-", 2)]
        dt = datetime(year=y, month=m, day=dd).date()
        return "upcoming" if dt > today else "released"
    except Exception:
        return "upcoming"



    start = content.find("[")
    end = content.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        obj = json.loads(content[start : end + 1])
        return list(obj) if isinstance(obj, list) else []
    except Exception:
        return []


def _call_qwen(client, model: str, prompt: str, enable_search: bool) -> str:
    extra: dict[str, Any] = {}
    if enable_search:
        extra = {"enable_search": True, "search_options": {"forced_search": True}}
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        extra_body=extra,
    )
    return str(completion.choices[0].message.content or "").strip()


def run_catalyst(cfg: MySQLConfig, _mode: str | None, params: dict[str, Any] | None) -> JobStats:
    dashscope_key = str((params or {}).get("dashscope_api_key") or os.getenv("DASHSCOPE_API_KEY", "")).strip()
    if not dashscope_key:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="qwen_search",
            fallback_chain=["qwen_search"],
            message="缺少 DASHSCOPE_API_KEY",
        )

    prompt_file = str((params or {}).get("prompts_yaml") or os.getenv("AI_QUANT_CATALYST_PROMPTS_YAML", "")).strip()
    search_prompt_tpl = None
    prompts_prompt_tpl = None
    if prompt_file:
        import yaml

        with open(prompt_file, "r", encoding="utf-8") as f:
            cfg_yaml = yaml.safe_load(f) or {}
        cal = (cfg_yaml.get("calendar") or {}) if isinstance(cfg_yaml, dict) else {}
        search_prompt_tpl = cal.get("search_catalysts")
        prompts_prompt_tpl = cal.get("generate_prompts")

    if not search_prompt_tpl or not prompts_prompt_tpl:
        search_prompt_tpl = (
            "请联网搜索 {start_date} 到 {end_date} 之间可能影响中国A股市场的关键宏观/政策/行业催化剂事件，"
            "输出严格 JSON 数组，每个元素包含 date(YYYY-MM-DD), title, country, category, importance(1-3)。"
        )
        prompts_prompt_tpl = (
            "你将得到一组事件 JSON。请为每个事件生成一个用于进一步分析的中文提示词 prompt。"
            "输出严格 JSON 数组，每个元素包含 title 与 prompt。\n\n{events_json}"
        )

    model = str(os.getenv("QWEN_MODEL", "qwen-max")).strip() or "qwen-max"
    from openai import OpenAI

    client = OpenAI(api_key=dashscope_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

    today = datetime.now().date()
    start_date = today.isoformat()
    end_date = (today + timedelta(days=180)).isoformat()
    prompt = str(search_prompt_tpl).format(start_date=start_date, end_date=end_date)

    content = _call_qwen(client, model, prompt, enable_search=True)
    events = _parse_json_array(content)
    if not events:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="qwen_search",
            fallback_chain=["qwen_search"],
            message="未解析到事件 JSON 数组",
        )

    brief = [{"date": e.get("date", ""), "title": e.get("title", ""), "country": e.get("country", "")} for e in events]
    prompts_map: dict[str, str] = {}
    for i in range(0, len(brief), 20):
        batch = brief[i : i + 20]
        p = str(prompts_prompt_tpl).format(events_json=json.dumps(batch, ensure_ascii=False, indent=2))
        res = _parse_json_array(_call_qwen(client, model, p, enable_search=False))
        for r in res:
            t = str(r.get("title", "")).strip()
            ap = str(r.get("prompt", "")).strip()
            if t and ap:
                prompts_map[t] = ap

    conn = connect(cfg)
    try:
        existing = query_dict(conn, "SELECT event_date, title FROM trade_calendar_event WHERE source=%s", ("qwen_search",))
        existing_keys = {(to_ymd(r.get("event_date")) or "", str(r.get("title") or "")) for r in existing}

        rows: list[tuple[Any, ...]] = []
        for evt in events:
            d = to_ymd(evt.get("date"))
            title = str(evt.get("title") or "").strip()
            if not d or not title:
                continue
            key = (d, title)
            if key in existing_keys:
                continue
            country = _country_code(str(evt.get("country") or "中国"))
            category = str(evt.get("category") or "policy").strip() or "policy"
            imp = int(evt.get("importance") or 2)
            if imp < 1:
                imp = 1
            if imp > 3:
                imp = 3
            rows.append(
                (
                    d,
                    None,
                    country,
                    category[:30],
                    title[:200],
                    imp,
                    None,
                    None,
                    None,
                    None,
                    prompts_map.get(title),
                    "qwen_search",
                    None,
                    _status_by_date(d),
                )
            )

        written = executemany(conn, _INSERT_SQL, rows)
        return JobStats(
            items_processed=len(rows),
            rows_written=written,
            failed_items=[],
            data_source_final="qwen_search",
            fallback_chain=["qwen_search"],
            message=None,
        )
    finally:
        conn.close()
