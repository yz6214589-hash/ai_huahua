from __future__ import annotations

from datetime import datetime
import os
from typing import Any

import pandas as pd
from openai import OpenAI

from ..db import MySQLConfig, connect, execute, query_dict
from ..models import DataSource
from .common import JobStats


POSITIVE_WORDS = ["涨停", "大涨", "利好", "增长", "突破", "新高", "预增", "增持", "盈利", "超预期", "重大突破", "战略合作", "中标"]
NEGATIVE_WORDS = ["跌停", "大跌", "利空", "下降", "跌破", "新低", "预减", "减持", "亏损", "违规", "处罚", "退市", "暴雷", "爆仓"]
IMPORTANT_WORDS = ["资产重组", "业绩预增", "业绩预减", "高送转", "股权激励", "定向增发", "股东减持", "股东增持", "重大合同", "中标", "收购", "并购", "停牌", "复牌", "退市", "回购"]


def _sentiment(title: str) -> str:
    for w in POSITIVE_WORDS:
        if w in title:
            return "positive"
    for w in NEGATIVE_WORDS:
        if w in title:
            return "negative"
    return "neutral"


def _important(title: str) -> int:
    for w in IMPORTANT_WORDS:
        if w in title:
            return 1
    return 0


INSERT_SQL = """
INSERT INTO trade_stock_news
(stock_code, news_type, title, content, summary, source, source_url, sentiment, is_important, published_at)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""


def _get_llm_client() -> tuple[OpenAI, str] | None:
    kimi_key = os.getenv("KIMI_API_KEY")
    if kimi_key and str(kimi_key).strip():
        base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
        model = os.getenv("KIMI_MODEL", "kimi-latest")
        return OpenAI(api_key=str(kimi_key).strip(), base_url=str(base_url).strip()), model
    dash_key = os.getenv("DASHSCOPE_API_KEY")
    if dash_key and str(dash_key).strip():
        model = os.getenv("QWEN_MODEL", "qwen-max")
        return OpenAI(api_key=str(dash_key).strip(), base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"), model
    return None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        import json

        return json.loads(text[start : end + 1])
    except Exception:
        return None


def _summarize_with_llm(client: OpenAI, model: str, title: str, content: str) -> tuple[str | None, str | None]:
    prompt = (
        "你是量化交易系统的新闻清洗员。请基于标题与正文，输出严格 JSON 对象，仅包含两个字段："
        "summary(中文，<=80字，客观概括，不要引号) 与 sentiment(positive/negative/neutral)。\n\n"
        f"title: {title}\n\ncontent: {content[:1200]}"
    )
    resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
    text = resp.choices[0].message.content or ""
    obj = _extract_json_object(text)
    if not obj:
        return None, None
    summary = str(obj.get("summary", "")).strip() or None
    sentiment = str(obj.get("sentiment", "")).strip() or None
    if sentiment not in ("positive", "negative", "neutral"):
        sentiment = None
    return summary, sentiment


def run_stock_news(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    import akshare as ak

    test_mode = (mode or "").lower() == "test"
    test_stock = (params or {}).get("test_stock") or "600519.SH"
    max_stocks = int((params or {}).get("max_stocks") or (1 if test_mode else 200))
    enable_llm = bool((params or {}).get("enable_llm_summary", True))

    llm = _get_llm_client() if enable_llm else None

    conn = connect(cfg)
    try:
        all_rows = query_dict(conn, "SELECT DISTINCT stock_code FROM trade_stock_daily")
        all_codes = [str(r["stock_code"]) for r in all_rows]
        if test_mode:
            all_codes = [test_stock]
        else:
            all_codes = all_codes[:max_stocks]

        today_rows = query_dict(conn, "SELECT DISTINCT stock_code FROM trade_stock_news WHERE DATE(created_at)=CURDATE()")
        today_done = {str(r["stock_code"]) for r in today_rows if r.get("stock_code")}

        existing_titles_rows = query_dict(conn, "SELECT title FROM trade_stock_news")
        existing_titles = {str(r["title"]) for r in existing_titles_rows if r.get("title")}

        processed = 0
        written = 0
        failed: list[str] = []
        for code in all_codes:
            processed += 1
            if code in today_done:
                continue
            code_num = code.split(".")[0]
            try:
                df = ak.stock_news_em(symbol=code_num)
            except Exception:
                failed.append(code)
                continue
            if df is None or len(df) == 0:
                continue

            for _, row in df.iterrows():
                title = str(row.get("新闻标题", "")).strip()
                if not title or title in existing_titles:
                    continue
                content = str(row.get("新闻内容", "")).strip()
                url = str(row.get("新闻链接", "")).strip()
                pub_time = str(row.get("发布时间", "")).strip()
                source = str(row.get("文章来源", "")).strip() or "eastmoney"
                published_at = None
                if pub_time:
                    try:
                        published_at = pd.to_datetime(pub_time, errors="coerce")
                        if pd.isna(published_at):
                            published_at = None
                        else:
                            published_at = published_at.to_pydatetime()
                    except Exception:
                        published_at = None

                summary = None
                sentiment = _sentiment(title)
                if llm and content:
                    try:
                        s, sen = _summarize_with_llm(llm[0], llm[1], title, content)
                        summary = s
                        if sen:
                            sentiment = sen
                    except Exception:
                        pass

                try:
                    affected = execute(
                        conn,
                        INSERT_SQL,
                        (
                            code,
                            "news",
                            title,
                            content[:2000] if content else "",
                            summary,
                            source,
                            url or None,
                            sentiment,
                            _important(title),
                            published_at,
                        ),
                    )
                    if affected:
                        written += 1
                        existing_titles.add(title)
                except Exception:
                    existing_titles.add(title)

            conn.commit()

        return JobStats(
            items_processed=processed,
            rows_written=written,
            failed_items=failed,
            data_source_final=DataSource.akshare,
            fallback_chain=[DataSource.akshare],
            message=None if not failed else f"失败 {len(failed)} 只股票",
        )
    finally:
        conn.close()

