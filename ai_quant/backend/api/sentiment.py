from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter

from core.data import get_watchlist
from core.db import load_mysql_config, connect, query_dict, execute
from infra.storage.logging_service import get_logger
from infra.storage import sentiment_store as store

from pathlib import Path
import sys

# 将 sentiment_scorer 脚本目录加入 sys.path，以便直接 import
_LLM_SKILL_DIR = Path(__file__).resolve().parents[1] / "llm" / "skills" / "sentiment-analysis" / "scripts"
if str(_LLM_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_LLM_SKILL_DIR))

from sentiment_scorer import init_client, analyze_single_news, extract_news_text as _extract_news_text

logger = get_logger("sentiment")

router = APIRouter(prefix="/api/v1", tags=["sentiment"])


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _pick_watchlist_codes() -> tuple[list[str], list[str]]:
    data = get_watchlist()
    items = data.get("items") if isinstance(data, dict) else []
    codes: list[str] = []
    names: list[str] = []
    for it in items if isinstance(items, list) else []:
        code = str((it or {}).get("stock_code") or "").strip().upper()
        if not code:
            continue
        name = str((it or {}).get("stock_name") or "").strip()
        codes.append(code)
        names.append(name or code)
    return codes, names


# 关键词分类规则
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
    # 使用 sentiment_scorer 的 extract_news_text 提取文本
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


@router.get("/sentiment/schedule")
def sentiment_schedule_get() -> dict[str, Any]:
    return store.get_schedule()


@router.put("/sentiment/schedule")
def sentiment_schedule_put(body: dict[str, Any]) -> dict[str, Any]:
    current = store.get_schedule()
    enabled = bool(body.get("enabled", current.get("enabled", True)))
    cron = str(body.get("cron") or current.get("cron", "10 15 * * 1-5")).strip()
    timezone = str(body.get("timezone") or current.get("timezone", "Asia/Shanghai")).strip() or "Asia/Shanghai"
    frequency = str(body.get("frequency") or current.get("frequency", "daily")).strip() or "daily"
    market_time = str(body.get("market_time") or current.get("market_time", "14:00")).strip() or "14:00"
    fixed_time = str(body.get("fixed_time") or current.get("fixed_time", "15:10")).strip() or "15:10"
    updated = {
        "enabled": enabled,
        "cron": cron,
        "timezone": timezone,
        "frequency": frequency,
        "market_time": market_time,
        "fixed_time": fixed_time,
    }
    store.save_schedule(updated)
    # 同步写入 MySQL（非阻塞，失败不影响主流程）
    store.save_schedule_to_mysql(updated)
    logger.info("舆情调度配置已更新", extra={
        "enabled": enabled,
        "cron": cron,
        "timezone": timezone,
        "frequency": frequency,
        "market_time": market_time,
        "fixed_time": fixed_time,
    })
    return store.get_schedule()


@router.get("/sentiment/runs")
def sentiment_runs_list(limit: str = "20") -> dict[str, Any]:
    # Bug 3 修复: limit 参数类型改为 str，内部自行转换，避免非数字字符串触发 422
    try:
        limit_val = int(limit)
    except (ValueError, TypeError):
        limit_val = 20
    return {"runs": store.list_runs(limit=limit_val)}


@router.post("/sentiment/runs")
def sentiment_run_create(body: dict[str, Any]) -> dict[str, Any]:
    logger.info("舆情扫描任务创建", extra={
        "stock_codes": body.get("stock_codes"),
        "days": body.get("days"),
        "use_llm": body.get("use_llm")
    })
    raw_codes = body.get("stock_codes")
    if isinstance(raw_codes, list):
        stock_codes = [str(x or "").strip().upper() for x in raw_codes if str(x or "").strip()]
    else:
        stock_codes = []
    stock_names: list[str] = []
    if stock_codes:
        # Bug 5 修复: 从 trade_stock_master 表查询股票中文名称，查询失败时 fallback 为代码
        try:
            cfg = load_mysql_config()
            conn = connect(cfg)
            try:
                name_map: dict[str, str] = {}
                for code in stock_codes:
                    rows = query_dict(
                        conn,
                        "SELECT stock_name FROM trade_stock_master WHERE stock_code = %s LIMIT 1",
                        (code,),
                    )
                    name_map[code] = rows[0]["stock_name"] if rows else code
                stock_names = [name_map.get(c, c) for c in stock_codes]
            finally:
                conn.close()
        except Exception as e:
            logger.warning("查询股票名称失败，使用代码作为名称", extra={"error": str(e)})
            stock_names = [str(x) for x in stock_codes]
    else:
        stock_codes, stock_names = _pick_watchlist_codes()

    run_id = uuid4().hex
    logger.info("舆情扫描开始", extra={
        "run_id": run_id,
        "stock_codes_count": len(stock_codes)
    })

    created_at = _now_iso()
    # Bug 1 修复: days 传入非数字字符串时，int() 转换失败使用默认值 3
    # Bug 2 修复: days 增加 1~30 范围限制，与 sentiment_monitor.py 保持一致
    try:
        days = int(body.get("days") or 3)
    except (ValueError, TypeError):
        days = 3
    days = max(1, min(30, days))
    run = {
        "run_id": run_id,
        "trigger": "manual",
        "stock_codes": stock_codes,
        "stock_names": stock_names,
        "days": days,
        "use_llm": bool(body.get("use_llm", False)),
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

    # 从 trade_stock_news 查询真实新闻
    use_llm = bool(body.get("use_llm", False))
    llm_client = None
    if use_llm:
        try:
            llm_client = init_client()
            logger.info("LLM 客户端初始化成功，将使用 LLM 精检", extra={"run_id": run_id})
        except Exception as e:
            logger.warning("LLM 客户端初始化失败，回退到关键词分类", extra={"error": str(e)})
            use_llm = False

    event_count = 0
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            for code, name in zip(stock_codes, stock_names):
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
        finally:
            conn.close()
    except Exception as e:
        logger.error("舆情新闻查询失败", extra={"error": str(e)})
        for code, name in zip(stock_codes, stock_names):
            evt = _build_no_news_event(run_id, code, name, created_at)
            store.write_event(evt)
            # 同步写入 MySQL
            store.write_event_to_mysql(evt)
            event_count += 1

    finished_at = _now_iso()
    run["status"] = "success"
    run["total_events"] = event_count
    run["finished_at"] = finished_at
    store.write_run(run)
    # 同步更新 MySQL
    store.write_run_to_mysql(run)

    logger.info("舆情扫描完成", extra={
        "run_id": run_id,
        "total_events": event_count,
    })
    return {"ok": True, "run": store.read_run(run_id)}


@router.get("/sentiment/events")
def sentiment_events_list(
    run_id: str | None = None,
    limit: str = "200",
    q: str | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    # Bug 3 修复: limit 参数类型改为 str，内部自行转换，避免非数字字符串触发 422
    try:
        limit_val = int(limit)
    except (ValueError, TypeError):
        limit_val = 200
    events = store.list_events(
        run_id=run_id,
        limit=limit_val,
        q=q,
        event_type=event_type,
    )
    return {"events": events}


@router.get("/macro/latest")
def macro_latest() -> dict[str, Any]:
    return store.get_macro_data()


# 指标名称映射
_INDICATOR_NAMES: dict[str, str] = {
    "CPI": "CPI（居民消费价格指数）",
    "PMI": "PMI（采购经理指数）",
    "LPR": "LPR（贷款市场报价利率）",
    "VIX": "VIX（CBOE波动率指数）",
    "iVIX": "iVIX（中国波动率指数）",
    "OVX": "OVX（原油波动率指数）",
    "GVZ": "GVZ（黄金波动率指数）",
    "US10Y": "美国10年期国债收益率",
    "FearGreed": "恐惧贪婪指数",
}

# FRED 指标对应的 series_id 映射
_FRED_SERIES: dict[str, str] = {
    "VIX": "VIXCLS",
    "OVX": "OVXCLS",
    "GVZ": "GVZCLS",
    "US10Y": "DGS10",
}


@router.get("/macro/history/{indicator}")
def macro_history(indicator: str, days: str = "90") -> dict[str, Any]:
    """
    返回指定指标的历史数据，用于前端绘制趋势图表。
    支持指标: CPI, PMI, LPR, VIX, iVIX, OVX, GVZ, US10Y, FearGreed
    """
    # days 参数处理
    try:
        days_val = int(days)
    except (ValueError, TypeError):
        days_val = 90
    days_val = max(7, min(365, days_val))

    name = _INDICATOR_NAMES.get(indicator, indicator)
    data: list[dict[str, Any]] = []

    # --- CPI / PMI / LPR: 从 trade_macro_indicator 宽表查询 ---
    if indicator == "CPI":
        sql = (
            "SELECT indicator_date, cpi_yoy AS value "
            "FROM trade_macro_indicator "
            "WHERE cpi_yoy IS NOT NULL "
            "AND indicator_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
            "ORDER BY indicator_date"
        )
        data = _query_macro_history(sql, days_val)
    elif indicator == "PMI":
        sql = (
            "SELECT indicator_date, pmi AS value "
            "FROM trade_macro_indicator "
            "WHERE pmi IS NOT NULL "
            "AND indicator_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
            "ORDER BY indicator_date"
        )
        data = _query_macro_history(sql, days_val)
    elif indicator == "LPR":
        sql = (
            "SELECT indicator_date, lpr_1y AS value "
            "FROM trade_macro_indicator "
            "WHERE lpr_1y IS NOT NULL "
            "AND indicator_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
            "ORDER BY indicator_date"
        )
        data = _query_macro_history(sql, days_val)

    # --- VIX / OVX / GVZ / US10Y: 从 FRED 获取历史 CSV ---
    elif indicator in _FRED_SERIES:
        data = store._fred_history(_FRED_SERIES[indicator], days_val)

    # --- FearGreed: 优先从 CNN 获取，降级使用 VIX 计算 ---
    elif indicator == "FearGreed":
        cnn_data = store._fetch_cnn_fear_greed_history(days_val)
        if cnn_data:
            data = cnn_data
        else:
            # 降级: 基于 VIX 历史数据计算
            vix_data = store._fred_history("VIXCLS", days_val)
            for point in vix_data:
                score = store._compute_fear_greed(point["value"])
                if score is not None:
                    data.append({"date": point["date"], "value": score})

    # --- iVIX: 从 akshare 获取历史数据 ---
    elif indicator == "iVIX":
        data = store._fetch_ivix_history(days_val)

    return {
        "indicator": indicator,
        "name": name,
        "data": data,
    }


def _query_macro_history(sql: str, days_val: int) -> list[dict[str, Any]]:
    """从 trade_macro_indicator 宽表查询历史数据"""
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(conn, sql, (days_val,))
            return [
                {"date": str(r.get("indicator_date", ""))[:10], "value": float(r["value"])}
                for r in rows
                if r.get("value") is not None
            ]
        finally:
            conn.close()
    except Exception as e:
        logger.warning("宏观历史数据查询失败", extra={"error": str(e)})
        return []


@router.get("/sentiment/stock-list")
def get_sentiment_stock_list() -> dict[str, Any]:
    """查询舆情监控系统的独立股票列表"""
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(
                conn,
                "SELECT stock_code, stock_name, added_at, notes FROM sentiment_stock_list ORDER BY added_at DESC",
            )
            return {"items": rows if rows else []}
        finally:
            conn.close()
    except Exception as e:
        logger.warning("查询舆情股票列表失败", extra={"error": str(e)})
        return {"items": []}


@router.post("/sentiment/stock-list/sync")
def sync_from_watchlist() -> dict[str, Any]:
    """
    从通用自选库同步股票到舆情监控股票列表。
    @标识规则：带 @ 的股票保持不动，无 @ 的追加
    """
    added_count = 0
    skipped_count = 0
    try:
        watchlist_data = get_watchlist()
        watchlist_items = watchlist_data.get("items") if isinstance(watchlist_data, dict) else []
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            existing_rows = query_dict(conn, "SELECT stock_code, stock_name FROM sentiment_stock_list")
            existing_codes = set()
            for r in existing_rows or []:
                code = str(r.get("stock_code", "")).strip()
                if code.startswith("@"):
                    existing_codes.add(code[1:].strip())
                else:
                    existing_codes.add(code)
            for it in watchlist_items if isinstance(watchlist_items, list) else []:
                code = str((it or {}).get("stock_code") or "").strip().upper()
                if not code:
                    skipped_count += 1
                    continue
                name = str((it or {}).get("stock_name") or "").strip()
                if code in existing_codes:
                    skipped_count += 1
                    continue
                try:
                    execute(conn, "INSERT INTO sentiment_stock_list (stock_code, stock_name) VALUES (%s, %s)", (code, name or code))
                    added_count += 1
                except Exception as e:
                    logger.warning("插入舆情股票失败: %s", str(e))
                    skipped_count += 1
            updated_rows = query_dict(conn, "SELECT stock_code, stock_name, added_at, notes FROM sentiment_stock_list ORDER BY added_at DESC")
            return {"items": updated_rows if updated_rows else [], "added_count": added_count, "skipped_count": skipped_count, "total": len(updated_rows or [])}
        finally:
            conn.close()
    except Exception as e:
        logger.warning("从自选库同步舆情股票列表失败", extra={"error": str(e)})
        return {"items": [], "added_count": 0, "skipped_count": 0, "total": 0, "error": str(e)}
