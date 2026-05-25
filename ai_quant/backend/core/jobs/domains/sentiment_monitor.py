from __future__ import annotations

from typing import Any

from core.db import MySQLConfig, connect, query_dict, load_mysql_config
from core.data import get_watchlist
from core.jobs.common import JobStats
from core.jobs.domains.stock_group import get_stock_codes_by_scope, ensure_stock_group_tables
from infra.storage import sentiment_store as store
from infra.storage.logging_service import get_logger

from pathlib import Path
import sys

_LLM_SKILL_DIR = Path(__file__).resolve().parents[3] / "llm" / "skills" / "sentiment-analysis" / "scripts"
if str(_LLM_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_LLM_SKILL_DIR))

from sentiment_scorer import init_client, analyze_single_news, extract_news_text as _extract_news_text

logger = get_logger("sentiment_monitor")

# 关键词分类规则（与 api/sentiment.py 保持一致）
_POSITIVE_KEYWORDS = ["业绩预增", "增持", "回购", "利好", "涨停", "突破", "新高", "上涨", "签约", "中标", "获批"]
_NEGATIVE_KEYWORDS = ["业绩预减", "减持", "处罚", "利空", "跌停", "亏损", "下滑", "违规", "退市", "暴雷", "风险"]
_POLICY_KEYWORDS = ["政策", "规划", "补贴", "改革", "监管", "法规", "国务院", "证监会", "央行"]


def _classify_news_event(run_id: str, stock_code: str, stock_name: str, news: dict, created_at: str) -> dict:
    """根据关键词对新闻进行基础分类"""
    title = str(news.get("title") or "")
    content = str(news.get("content") or "")[:500]
    text = title + content

    event_type = "中性"
    confidence = 0.5
    for kw in _POSITIVE_KEYWORDS:
        if kw in text:
            event_type = "利好"
            confidence = 0.7
            break
    for kw in _NEGATIVE_KEYWORDS:
        if kw in text:
            event_type = "利空"
            confidence = 0.7
            break
    for kw in _POLICY_KEYWORDS:
        if kw in text:
            event_type = "政策"
            confidence = 0.6
            break

    return {
        "run_id": run_id,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "source_type": news.get("news_type", "news"),
        "source_title": title[:255],
        "source_url": news.get("source_url"),
        "published_at": str(news.get("published_at") or created_at),
        "event_type": event_type,
        "event_category": "新闻扫描",
        "signal": "关注" if event_type == "利好" else "警惕" if event_type == "利空" else "观察",
        "signal_reason": f"关键词匹配: {event_type}",
        "impact": "待评估",
        "confidence": confidence,
        "urgency": "高" if event_type == "利空" else "低",
    }


def _build_no_news_event(run_id: str, stock_code: str, stock_name: str, created_at: str) -> dict:
    """无新闻时创建占位事件"""
    return {
        "run_id": run_id,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "source_type": "system",
        "source_title": "暂无近期舆情",
        "source_url": None,
        "published_at": created_at,
        "event_type": "中性",
        "event_category": "例行扫描",
        "signal": "观察",
        "signal_reason": "未发现近期新闻",
        "impact": "暂无显著影响",
        "confidence": 0.3,
        "urgency": "低",
    }


def _llm_classify_news(run_id: str, stock_code: str, stock_name: str, news: dict, created_at: str, llm_client) -> dict:
    """使用 LLM 对新闻进行情感分析并生成事件记录"""
    title = str(news.get("title") or "")
    content = str(news.get("content") or "")
    text = _extract_news_text({"title": title, "content": content})
    if not text.strip():
        text = title + " " + content[:500]

    try:
        result = analyze_single_news(llm_client, text[:2000])
    except Exception as e:
        logger.warning("LLM 情感分析失败，回退到关键词分类", extra={"stock_code": stock_code, "error": str(e)})
        return _classify_news_event(run_id, stock_code, stock_name, news, created_at)

    sentiment_map = {"正面": "利好", "负面": "利空", "中性": "中性"}
    event_type = sentiment_map.get(result.get("sentiment", "中性"), "中性")
    strength = max(1, min(5, int(result.get("strength", 3) or 3)))
    confidence = strength / 5.0
    impact = str(result.get("market_impact") or result.get("summary") or "待评估")

    return {
        "run_id": run_id,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "source_type": news.get("news_type", "news"),
        "source_title": title[:255],
        "source_url": news.get("source_url"),
        "published_at": str(news.get("published_at") or created_at),
        "event_type": event_type,
        "event_category": "LLM 精检",
        "signal": "关注" if event_type == "利好" else "警惕" if event_type == "利空" else "观察",
        "signal_reason": str(result.get("summary") or f"LLM 分析: {event_type}"),
        "impact": impact,
        "confidence": round(confidence, 2),
        "urgency": "高" if event_type == "利空" else "低",
    }


def run_sentiment_monitor(_cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    from datetime import datetime
    from uuid import uuid4

    days = max(1, min(30, int((params or {}).get("days") or 3)))
    scope_type = str((params or {}).get("scope_type") or "watchlist").strip().lower()
    group_id = int((params or {}).get("group_id") or 0)

    codes: list[str] = []
    names: list[str] = []
    if scope_type == "group":
        ensure_stock_group_tables()
        codes = get_stock_codes_by_scope("group", group_id=group_id)
        names = list(codes)
    else:
        # watchlist / all 默认使用自选股
        wl = get_watchlist()
        items = wl.get("items") if isinstance(wl, dict) else []
        for it in items if isinstance(items, list) else []:
            code = str((it or {}).get("stock_code") or "").strip().upper()
            if code:
                codes.append(code)
                name = str((it or {}).get("stock_name") or "").strip()
                names.append(name or code)
    if not codes:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="file",
            fallback_chain=["file"],
            message="自选股为空，无法扫描",
        )

    # 创建运行记录
    run_id = uuid4().hex
    created_at = datetime.now().isoformat(timespec="seconds")
    run = {
        "run_id": run_id,
        "trigger": "schedule",
        "stock_codes": codes,
        "stock_names": names,
        "days": days,
        "use_llm": False,
        "status": "running",
        "total_events": 0,
        "created_at": created_at,
        "started_at": created_at,
        "finished_at": None,
        "error_message": None,
    }
    store.write_run(run)
    # 同步写入 MySQL（非阻塞，失败不影响主流程）
    store.write_run_to_mysql(run)

    # 初始化 LLM 客户端（如果配置启用）
    use_llm = bool((params or {}).get("use_llm", False))
    llm_client = None
    if use_llm:
        try:
            llm_client = init_client()
            logger.info("LLM 客户端初始化成功", extra={"run_id": run_id})
        except Exception as e:
            logger.warning("LLM 客户端初始化失败，回退到关键词分类", extra={"error": str(e)})
            use_llm = False

    # 从 trade_stock_news 查询真实新闻
    event_count = 0
    rows_written = 0
    failed: list[str] = []
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            for code, name in zip(codes, names):
                try:
                    news_rows = query_dict(
                        conn,
                        """SELECT title, content, source, source_url, published_at, news_type
                           FROM trade_stock_news
                           WHERE stock_code = %s
                           AND published_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                           ORDER BY published_at DESC
                           LIMIT 20""",
                        (code, days),
                    )
                except Exception:
                    failed.append(code)
                    continue
                if not news_rows:
                    evt = _build_no_news_event(run_id, code, name, created_at)
                    store.write_event(evt)
                    # 同步写入 MySQL
                    store.write_event_to_mysql(evt)
                    event_count += 1
                    continue
                for news in news_rows:
                    if use_llm and llm_client:
                        evt = _llm_classify_news(run_id, code, name, news, created_at, llm_client)
                    else:
                        evt = _classify_news_event(run_id, code, name, news, created_at)
                    store.write_event(evt)
                    # 同步写入 MySQL
                    store.write_event_to_mysql(evt)
                    event_count += 1
                    rows_written += 1
        finally:
            conn.close()
    except Exception as e:
        logger.error("定时舆情扫描查询失败", extra={"error": str(e)})
        for code, name in zip(codes, names):
            evt = _build_no_news_event(run_id, code, name, created_at)
            store.write_event(evt)
            # 同步写入 MySQL
            store.write_event_to_mysql(evt)
            event_count += 1

    # 更新运行记录
    finished_at = datetime.now().isoformat(timespec="seconds")
    run["status"] = "success"
    run["total_events"] = event_count
    run["finished_at"] = finished_at
    store.write_run(run)
    # 同步更新 MySQL
    store.write_run_to_mysql(run)

    msg = f"扫描完成（days={days}，stocks={len(codes)}，events={event_count}）"
    return JobStats(
        items_processed=len(codes),
        rows_written=rows_written,
        failed_items=failed,
        data_source_final="mysql",
        fallback_chain=["mysql"],
        message=msg,
    )
