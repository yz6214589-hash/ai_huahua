from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from .script_runner import get_project_root, run_python_script


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _default_output_dir() -> Path:
    root = get_project_root()
    return _ensure_dir(root / ".charles" / "assistant_output")


def _read_json_if_exists(path: Path, max_chars: int = 6000) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars]
    except Exception:
        return ""


@tool
def market_fear_index(output_dir: str | None = None, include_ashare: bool = False) -> str:
    """获取宏观恐慌/贪婪指数（VIX/OVX/GVZ/US10Y 等）并输出分析结果。

    Args:
        output_dir: 输出目录（默认 .charles/assistant_output）
        include_ashare: 是否包含A股维度指标
    """
    out_dir = Path(output_dir) if output_dir else _default_output_dir()
    _ensure_dir(out_dir)
    args = ["skills/sentiment-analysis/scripts/market_fear_index.py", "--output_dir", str(out_dir)]
    if include_ashare:
        args.append("--include_ashare")
    r = run_python_script(args, timeout=180)
    file_guess = None
    for f in sorted(out_dir.glob("fear_index_*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        file_guess = f
        break
    preview = _read_json_if_exists(file_guess) if file_guess else ""
    meta = {"output_file": str(file_guess) if file_guess else None, "returncode": r["code"]}
    return json.dumps({"meta": meta, "stdout": r["stdout"], "stderr": r["stderr"], "preview": preview}, ensure_ascii=False)


@tool
def polymarket_monitor(output_dir: str | None = None, keyword: str | None = None, min_volume: float = 0) -> str:
    """扫描 Polymarket 预测市场，输出地缘政治/宏观事件概率与资产映射建议。

    Args:
        output_dir: 输出目录（默认 .charles/assistant_output）
        keyword: 关键词（如 China/tariff/war），留空则扫描默认关键词集合
        min_volume: 最小交易量过滤（USDC）
    """
    out_dir = Path(output_dir) if output_dir else _default_output_dir()
    _ensure_dir(out_dir)
    args = ["skills/sentiment-analysis/scripts/polymarket_monitor.py", "--output_dir", str(out_dir)]
    if keyword:
        args.extend(["--keyword", keyword])
    if min_volume and float(min_volume) > 0:
        args.extend(["--min_volume", str(min_volume)])
    r = run_python_script(args, timeout=180)
    file_guess = None
    for f in sorted(out_dir.glob("polymarket_*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        file_guess = f
        break
    preview = _read_json_if_exists(file_guess) if file_guess else ""
    meta = {"output_file": str(file_guess) if file_guess else None, "returncode": r["code"]}
    return json.dumps({"meta": meta, "stdout": r["stdout"], "stderr": r["stderr"], "preview": preview}, ensure_ascii=False)


@tool
def news_fetcher(stock: str | None = None, keywords: str | None = None, days: int = 7, output_dir: str | None = None, include_cctv: bool = False) -> str:
    """抓取新闻/公告，支持 stock 和 keywords 与 days 过滤，输出 news_file。

    Args:
        stock: 股票代码（如 002594、600519），可为空
        keywords: 关键词（逗号分隔），可为空
        days: 最近 N 天
        output_dir: 输出目录（默认 .charles/assistant_output）
        include_cctv: 是否附带央视新闻
    """
    out_dir = Path(output_dir) if output_dir else _default_output_dir()
    _ensure_dir(out_dir)
    kw = (keywords or "").strip()
    st = (stock or "").strip()
    if not kw and not st:
        kw = "A股,上证,政策,央行,降准,降息"
    args = [
        "skills/sentiment-analysis/scripts/news_fetcher.py",
        "--days",
        str(int(days or 7)),
        "--output_dir",
        str(out_dir),
    ]
    if st:
        args.extend(["--stock", st])
    if kw:
        args.extend(["--keywords", kw])
    if include_cctv:
        args.append("--include_cctv")
    r = run_python_script(args, timeout=180)
    try:
        last_line = (r["stdout"].splitlines() or [""])[-1]
        news_file = last_line.strip() if last_line.strip().endswith(".json") else None
    except Exception:
        news_file = None
    meta = {"news_file": news_file, "returncode": r["code"]}
    return json.dumps({"meta": meta, "stdout": r["stdout"], "stderr": r["stderr"]}, ensure_ascii=False)


@tool
def sentiment_scorer(news_file: str, output_dir: str | None = None, model: str = "qwen-turbo", max_news: int = 50) -> str:
    """对 news_file 执行情感分析并聚合 Fear&Greed 指数。

    Args:
        news_file: news_fetcher 输出的 JSON 文件路径
        output_dir: 输出目录（默认 .charles/assistant_output）
        model: 模型名（默认 qwen-turbo）
        max_news: 最大分析条数
    """
    out_dir = Path(output_dir) if output_dir else _default_output_dir()
    _ensure_dir(out_dir)
    args = [
        "skills/sentiment-analysis/scripts/sentiment_scorer.py",
        "--news_file",
        news_file,
        "--output_dir",
        str(out_dir),
        "--model",
        model,
        "--max_news",
        str(int(max_news or 50)),
    ]
    r = run_python_script(args, timeout=300)
    sent_guess = None
    for f in sorted(out_dir.glob("*_news_sentiment.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        sent_guess = f
        break
    mood_guess = None
    for f in sorted(out_dir.glob("*_news_mood.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        mood_guess = f
        break
    preview = _read_json_if_exists(mood_guess) if mood_guess else (_read_json_if_exists(sent_guess) if sent_guess else "")
    meta = {
        "sentiment_file": str(sent_guess) if sent_guess else None,
        "mood_file": str(mood_guess) if mood_guess else None,
        "returncode": r["code"],
    }
    return json.dumps({"meta": meta, "stdout": r["stdout"], "stderr": r["stderr"], "preview": preview}, ensure_ascii=False)


@tool
def event_detector(news_file: str, output_dir: str | None = None, model: str = "qwen-turbo", use_llm: bool = False) -> str:
    """对 news_file 做事件识别与信号生成，输出 events_file。

    Args:
        news_file: news_fetcher 输出的 JSON 文件路径
        output_dir: 输出目录（默认 .charles/assistant_output）
        model: 模型名（默认 qwen-turbo）
        use_llm: 是否启用 LLM 精检（更慢但可能更准）
    """
    out_dir = Path(output_dir) if output_dir else _default_output_dir()
    _ensure_dir(out_dir)
    args = [
        "skills/sentiment-analysis/scripts/event_detector.py",
        "--news_file",
        news_file,
        "--output_dir",
        str(out_dir),
        "--model",
        model,
    ]
    if use_llm:
        args.append("--use_llm")
    r = run_python_script(args, timeout=300)
    events_guess = None
    for f in sorted(out_dir.glob("*_news_events.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        events_guess = f
        break
    preview = _read_json_if_exists(events_guess) if events_guess else ""
    meta = {"events_file": str(events_guess) if events_guess else None, "returncode": r["code"]}
    return json.dumps({"meta": meta, "stdout": r["stdout"], "stderr": r["stderr"], "preview": preview}, ensure_ascii=False)


@tool
def query_pdf(query: str, stock: str = "", index_dir: str = "data/vector_store") -> str:
    """从本地 PDF 研报/财报知识库检索信息（RAG）。

    Args:
        query: 查询问题
        stock: 股票代码（如 600519），留空搜索全部
        index_dir: 索引目录（默认 data/vector_store）
    """
    args = ["skills/read-pdf/scripts/query_report.py", "--index_dir", index_dir, "--query", query]
    if stock:
        args.extend(["--stock", stock])
    r = run_python_script(args, timeout=180)
    return json.dumps({"stdout": r["stdout"], "stderr": r["stderr"], "returncode": r["code"]}, ensure_ascii=False)


def require_dashscope_key() -> None:
    if not (os.getenv("DASHSCOPE_API_KEY") or "").strip():
        raise RuntimeError("DASHSCOPE_API_KEY required")

