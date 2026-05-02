from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def _parse_datetime(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def fetch_stock_news_and_notices(stock_code_6: str, *, days: int = 3, limit: int = 50) -> list[dict[str, Any]]:
    import akshare as ak

    now = datetime.now()
    cutoff = now - timedelta(days=max(1, int(days)))

    items: list[dict[str, Any]] = []

    try:
        df = ak.stock_news_em(symbol=stock_code_6)
        if df is not None and not df.empty:
            cols = list(df.columns)
            for _, row in df.head(limit).iterrows():
                r = row.to_dict()
                title = r.get("新闻标题") or r.get("title") or r.get("标题") or ""
                content = r.get("新闻内容") or r.get("content") or r.get("内容") or ""
                url = r.get("新闻链接") or r.get("url") or r.get("链接") or r.get("网址") or None
                published = r.get("发布时间") or r.get("date") or r.get("日期") or r.get("时间") or None
                dt = _parse_datetime(published)
                if dt and dt < cutoff:
                    continue
                items.append(
                    {
                        "source_type": "news",
                        "title": str(title)[:255],
                        "content": str(content),
                        "url": url,
                        "published_at": dt,
                        "raw": r,
                    }
                )
    except Exception:
        pass

    try:
        df2 = ak.stock_notice_report(symbol=stock_code_6)
        if df2 is not None and not df2.empty:
            for _, row in df2.head(limit).iterrows():
                r = row.to_dict()
                title = r.get("公告标题") or r.get("title") or r.get("标题") or ""
                url = r.get("公告链接") or r.get("url") or r.get("链接") or None
                published = r.get("公告日期") or r.get("date") or r.get("日期") or None
                dt = _parse_datetime(published)
                if dt and dt < cutoff:
                    continue
                items.append(
                    {
                        "source_type": "notice",
                        "title": str(title)[:255],
                        "content": "",
                        "url": url,
                        "published_at": dt,
                        "raw": r,
                    }
                )
    except Exception:
        pass

    seen = set()
    deduped: list[dict[str, Any]] = []
    for it in sorted(items, key=lambda x: x.get("published_at") or datetime(1970, 1, 1), reverse=True):
        key = (it.get("source_type"), (it.get("title") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    return deduped[:limit]

