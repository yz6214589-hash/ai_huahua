#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用联网搜索技能 - 基于 Tavily SDK，支持同步/异步两套接口

依赖:
    pip install tavily-python

用法:
    # 同步接口
    python search.py --query "贵州茅台最新股价" --topic stock --max-results 5

    # 异步接口（适合高并发场景）
    python search.py --query "半导体行业政策" --topic policy --async

    # 带缓存强制刷新
    python search.py --query "中芯国际分析师评级" --no-cache

环境变量:
    TAVILY_API_KEY  - Tavily API 密钥（可选，不提供时自动降级到 DuckDuckGo）
    TAVILY_TOPIC    - 默认搜索主题（general/news/finance）
    TAVILY_MAX_RESULTS - 默认最大结果数

License 合规说明:
    tavily-python: MIT License (https://github.com/tavily-ai/tavily-python)
    DuckDuckGo HTML API: 无需 Key，公开可用
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

try:
    import httpx
    import asyncio
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False


if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
logger = logging.getLogger("web-search-universal")

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(SKILL_ROOT, ".cache")
CACHE_TTL_SECONDS = 3600

TAVILY_FALLBACK_WARNING_LOGGED = False


def _ensure_cache_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_key(query: str, topic: str, max_results: int) -> str:
    raw = f"{query}:{topic}:{max_results}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _read_cache(key: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        if time.time() - mtime > CACHE_TTL_SECONDS:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(key: str, data: Dict[str, Any]) -> None:
    _ensure_cache_dir()
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Cache write failed: %s", e)


def _ddg_fallback_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    多路降级搜索 - 依次尝试 DuckDuckGo HTML、Bing RSS，返回第一个成功结果。
    所有接口均无需 API Key。

    合规说明：DuckDuckGo HTML / Bing RSS 均为公开接口，用于非商业场景属合理使用。
    """
    logger.warning("[Fallback] Tavily API 不可用，开始降级搜索")
    errors = []

    try:
        result = _ddg_search_impl(query, max_results)
        if result.get("results"):
            return result
        errors.append(f"DuckDuckGo: no results ({len(result.get('results', []))})")
    except Exception as e:
        errors.append(f"DuckDuckGo: {e}")

    try:
        result = _bing_rss_search_impl(query, max_results)
        if result.get("results"):
            return result
        errors.append(f"Bing RSS: no results ({len(result.get('results', []))})")
    except Exception as e:
        errors.append(f"Bing RSS: {e}")

    logger.error("[Fallback] 所有降级搜索均失败: %s", "; ".join(errors))
    return {
        "query": query,
        "topic": "general",
        "results": [],
        "used_fallback": True,
        "fallback_reason": f"All fallbacks failed: {'; '.join(errors)}",
        "error": "; ".join(errors),
    }


def _ddg_search_impl(query: str, max_results: int) -> Dict[str, Any]:
    import httpx
    import re
    import urllib.parse
    encoded_q = urllib.parse.quote(query)
    params = {"q": query, "kl": "wt-wt"}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    ddg_endpoints = [
        f"https://html.duckduckgo.com/html/?q={encoded_q}&kl=wt-wt",
        f"https://lite.duckduckgo.com/50x/?q={encoded_q}",
    ]
    for endpoint in ddg_endpoints:
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0), follow_redirects=True) as client:
                resp = client.get(endpoint, headers=headers)
                resp.raise_for_status()
                text = resp.text
            break
        except Exception:
            continue
    else:
        raise RuntimeError("All DuckDuckGo endpoints failed")
    pattern = re.compile(
        r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
        r'.*?<a class="result__snippet"[^>]*>([^<]+)</a>',
        re.DOTALL | re.IGNORECASE,
    )
    results: List[Dict[str, Any]] = []
    for match in pattern.finditer(text):
        url = match.group(1).strip()
        title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", match.group(3)).strip()
        results.append({
            "title": title[:200],
            "url": url,
            "content": snippet[:500],
            "published_date": None,
            "source": "DuckDuckGo",
        })
        if len(results) >= max_results:
            break
    if not results:
        simple = re.compile(r'href="(https?://[^"]+)"[^>]*>([^<]+)</a>', re.IGNORECASE)
        for m in simple.finditer(text):
            url = m.group(1)
            if url.startswith("http") and "duckduckgo" not in url:
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if title and len(results) < max_results:
                    results.append({
                        "title": title[:200],
                        "url": url,
                        "content": "",
                        "published_date": None,
                        "source": "DuckDuckGo",
                    })
    return {
        "query": query,
        "topic": "general",
        "results": results,
        "used_fallback": True,
        "fallback_reason": "TAVILY_API_KEY not configured",
    }


def _bing_rss_search_impl(query: str, max_results: int) -> Dict[str, Any]:
    import httpx
    import re
    import xml.etree.ElementTree as ET
    import urllib.parse
    encoded_q = urllib.parse.quote(query)
    bing_endpoints = [
        f"https://cn.bing.com/search?q={encoded_q}&format=rss",
        f"https://www.bing.com/search?q={encoded_q}&format=rss",
    ]
    text = ""
    for endpoint in bing_endpoints:
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0), follow_redirects=True) as client:
                resp = client.get(endpoint, headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xml",
                })
                resp.raise_for_status()
                text = resp.text
                if "<rss" not in text and "<feed" not in text:
                    raise RuntimeError("Not an RSS/Atom response")
                break
        except Exception:
            continue
    else:
        raise RuntimeError("All Bing endpoints failed")
    results: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
        for item in root.findall(".//item") + root.findall(".//entry"):
            title_el = item.find("title") or item.find("atom:title")
            link_el = item.find("link") or item.find("atom:link")
            desc_el = item.find("description") or item.find("atom:summary") or item.find("summary")
            date_el = item.find("pubDate") or item.find("published") or item.find("atom:published")
            results.append({
                "title": (title_el.text or "")[:200] if title_el is not None else "",
                "url": (link_el.get("href") or link_el.text or "") if link_el is not None else "",
                "content": (desc_el.text or "")[:500] if desc_el is not None else "",
                "published_date": (date_el.text or "") if date_el is not None else None,
                "source": "Bing Search",
            })
            if len(results) >= max_results:
                break
    except Exception:
        snippet_pattern = re.compile(r"<title>([^<]+)</title>.*?<link>([^<]+)</link>", re.DOTALL)
        for m in snippet_pattern.finditer(text[:3000]):
            results.append({
                "title": m.group(1).strip()[:200],
                "url": m.group(2).strip(),
                "content": "",
                "published_date": None,
                "source": "Bing Search",
            })
            if len(results) >= max_results:
                break
    return {
        "query": query,
        "topic": "general",
        "results": results,
        "used_fallback": True,
        "fallback_reason": "TAVILY_API_KEY not configured",
    }


def search(
    query: str,
    topic: str = "general",
    max_results: int = 5,
    use_cache: bool = True,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    同步搜索接口 - 通用联网搜索

    Args:
        query:        搜索查询字符串
        topic:        搜索主题 (general / news / finance)
        max_results:  最大返回结果数
        use_cache:    是否使用本地缓存（TTL = 1小时）
        api_key:      Tavily API Key（None 时从环境变量 TAVILY_API_KEY 读取）

    Returns:
        标准结构化 JSON:
        {
            "query": str,
            "topic": str,
            "results": [
                {
                    "title": str,        # 搜索结果标题
                    "url": str,          # 结果链接
                    "content": str,      # 摘要/内容片段
                    "published_date": str | None,  # 发布时间（若有）
                    "source": str        # 来源（DuckDuckGo / Tavily）
                }, ...
            ],
            "used_fallback": bool,
            "fallback_reason": str | None,
            "error": str | None,
            "cached": bool,
            "search_time_ms": int
        }
    """
    global TAVILY_FALLBACK_WARNING_LOGGED
    start = time.time()
    cache_hit = False
    error_msg: Optional[str] = None
    used_fallback = False
    fallback_reason: Optional[str] = None

    cache_key_val = _cache_key(query, topic, max_results)

    if use_cache:
        cached = _read_cache(cache_key_val)
        if cached:
            cached["cached"] = True
            elapsed_ms = int((time.time() - start) * 1000)
            cached["search_time_ms"] = elapsed_ms
            return cached

    effective_key = api_key or os.getenv("TAVILY_API_KEY")

    if not effective_key:
        if not TAVILY_FALLBACK_WARNING_LOGGED:
            logger.warning(
                "[WARN] TAVILY_API_KEY 未设置，搜索结果由 DuckDuckGo 提供（质量可能低于 Tavily）。"
                "如需 Tavily，请访问 https://app.tavily.com 注册并设置环境变量。"
            )
            TAVILY_FALLBACK_WARNING_LOGGED = True
        result = _ddg_fallback_search(query, max_results)
        result["cached"] = False
        result["search_time_ms"] = int((time.time() - start) * 1000)
        return result

    if not TAVILY_AVAILABLE:
        if not TAVILY_FALLBACK_WARNING_LOGGED:
            logger.warning(
                "[WARN] tavily-python 未安装，正在使用 DuckDuckGo 降级。"
                "执行 pip install tavily-python 以启用 Tavily 搜索。"
            )
            TAVILY_FALLBACK_WARNING_LOGGED = True
        result = _ddg_fallback_search(query, max_results)
        result["cached"] = False
        result["search_time_ms"] = int((time.time() - start) * 1000)
        return result

    try:
        client = TavilyClient(api_key=effective_key)
        response = client.search(
            query=query,
            topic=topic,
            max_results=max_results,
            include_answer=True,
            include_raw_content=False,
        )
        client.close()

        results: List[Dict[str, Any]] = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "published_date": item.get("published_date"),
                "source": "Tavily",
            })

        answer_text: Optional[str] = response.get("answer")
        if answer_text:
            results.insert(0, {
                "title": "Tavily AI 摘要答案",
                "url": "",
                "content": answer_text,
                "published_date": None,
                "source": "Tavily/AI",
            })

        result = {
            "query": query,
            "topic": topic,
            "results": results,
            "used_fallback": False,
            "cached": False,
            "search_time_ms": int((time.time() - start) * 1000),
        }

    except Exception as e:
        error_msg = str(e)
        logger.error("[Tavily] 搜索异常: %s，切换 DuckDuckGo 降级", error_msg)
        result = _ddg_fallback_search(query, max_results)
        result["error"] = error_msg
        result["cached"] = False
        result["search_time_ms"] = int((time.time() - start) * 1000)
        result["fallback_reason"] = f"Tavily error: {error_msg}"

    if use_cache and result.get("results"):
        _write_cache(cache_key_val, result)

    elapsed_ms = int((time.time() - start) * 1000)
    result["search_time_ms"] = elapsed_ms
    return result


async def async_search(
    query: str,
    topic: str = "general",
    max_results: int = 5,
    use_cache: bool = True,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """
    异步搜索接口 - 适合高并发 Agent 场景

    优先级同 sync 版本：Tavily API > DuckDuckGo Fallback。
    与 sync 版本共用同一缓存（cache 文件可跨进程共享）。

    Args:
        query:        搜索查询字符串
        topic:        搜索主题 (general / news / finance)
        max_results:  最大返回结果数
        use_cache:    是否使用本地缓存（TTL = 1小时）
        api_key:      Tavily API Key
        timeout:      单次请求超时（秒），默认 15s

    Returns:
        同 search() 返回值结构
    """
    global TAVILY_FALLBACK_WARNING_LOGGED
    start = time.time()

    if use_cache:
        cached = _read_cache(_cache_key(query, topic, max_results))
        if cached:
            cached["cached"] = True
            cached["search_time_ms"] = int((time.time() - start) * 1000)
            return cached

    effective_key = api_key or os.getenv("TAVILY_API_KEY")

    if not effective_key or not TAVILY_AVAILABLE:
        if not TAVILY_FALLBACK_WARNING_LOGGED:
            logger.warning(
                "[WARN] Tavily 不可用，使用 DuckDuckGo 异步降级搜索"
            )
            TAVILY_FALLBACK_WARNING_LOGGED = True
        result = _ddg_fallback_search(query, max_results)
        result["cached"] = False
        result["search_time_ms"] = int((time.time() - start) * 1000)
        return result

    try:
        import httpx
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {effective_key}",
            "X-Client-Source": "tavily-python-async",
        }
        payload = {
            "query": query,
            "topic": topic,
            "max_results": max_results,
            "include_answer": True,
            "include_raw_content": False,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            response = resp.json()

        results: List[Dict[str, Any]] = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "published_date": item.get("published_date"),
                "source": "Tavily",
            })
        answer_text = response.get("answer")
        if answer_text:
            results.insert(0, {
                "title": "Tavily AI 摘要答案",
                "url": "",
                "content": answer_text,
                "published_date": None,
                "source": "Tavily/AI",
            })
        result = {
            "query": query,
            "topic": topic,
            "results": results,
            "used_fallback": False,
            "cached": False,
            "search_time_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        logger.error("[Tavily Async] 异常: %s，降级到 DuckDuckGo", e)
        result = _ddg_fallback_search(query, max_results)
        result["error"] = str(e)
        result["cached"] = False
        result["search_time_ms"] = int((time.time() - start) * 1000)

    if use_cache and result.get("results"):
        _write_cache(_cache_key(query, topic, max_results), result)

    result["search_time_ms"] = int((time.time() - start) * 1000)
    return result


def batch_search(
    queries: List[str],
    topic: str = "general",
    max_results: int = 5,
    use_cache: bool = True,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    批量同步搜索 - 适用于需要对多个查询并行发起的场景。
    内部通过并发调用实现（非串行）。

    Returns:
        List[Dict]，每个元素为单个 query 的搜索结果，顺序与 queries 一致。
    """
    if not ASYNC_AVAILABLE:
        return [search(q, topic, max_results, use_cache, api_key) for q in queries]

    import concurrent.futures
    results: List[Dict[str, Any]] = [None] * len(queries)

    def worker(idx_q: tuple) -> tuple:
        idx, q = idx_q
        return idx, search(q, topic, max_results, use_cache, api_key)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(queries), 8)) as executor:
        futures = [executor.submit(worker, (i, q)) for i, q in enumerate(queries)]
        for future in concurrent.futures.as_completed(futures):
            idx, res = future.result()
            results[idx] = res

    return results


def _format_results_text(results: List[Dict[str, Any]]) -> str:
    if not results:
        return "（未找到相关结果）"
    lines = []
    for i, r in enumerate(results, 1):
        date_str = f"[{r['published_date']}] " if r.get("published_date") else ""
        source_str = f"({r.get('source', '')})" if r.get("source") else ""
        lines.append(f"[{i}] {date_str}{r.get('title', '')} {source_str}")
        lines.append(f"    URL: {r.get('url', '')}")
        content = r.get("content", "")
        if content:
            lines.append(f"    {content[:200]}")
        lines.append("")
    return "\n".join(lines)


def _cli_interactive(query: str, topic: str, max_results: int, use_cache: bool) -> None:
    print(f"\n{'=' * 70}")
    print(f"[web-search-universal] 查询: {query}")
    print(f"主题: {topic} | 最大结果数: {max_results} | 缓存: {'启用' if use_cache else '禁用'}")
    print(f"{'=' * 70}\n")
    result = search(query, topic, max_results, use_cache)
    print(_format_results_text(result.get("results", [])))
    print(f"[统计] 耗时: {result.get('search_time_ms', 0)} ms | "
          f"缓存: {'命中' if result.get('cached') else 'miss'} | "
          f"降级: {'是' if result.get('used_fallback') else '否'}")
    if result.get("error"):
        print(f"[错误] {result.get('error')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="通用联网搜索工具 - Tavily SDK + DuckDuckGo 降级",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--query", required=True, help="搜索查询字符串")
    parser.add_argument(
        "--topic",
        choices=["general", "news", "finance"],
        default="general",
        dest="topic",
        help="搜索主题: general=通用, news=新闻, finance=金融（默认 general）",
    )
    parser.add_argument(
        "--max-results", type=int, default=5, dest="max_results",
        help="最大返回结果数（默认 5）",
    )
    parser.add_argument(
        "--no-cache", action="store_true", dest="no_cache",
        help="禁用缓存，强制重新请求",
    )
    parser.add_argument(
        "--async", action="store_true", dest="use_async",
        help="使用异步接口（需要 ASYNC_AVAILABLE）",
    )
    parser.add_argument(
        "--output", dest="output",
        help="结果保存路径（JSON 格式，可选）",
    )
    parser.add_argument(
        "--api-key", dest="api_key",
        help="Tavily API Key（可选，优先使用环境变量 TAVILY_API_KEY）",
    )
    args = parser.parse_args()

    use_cache = not args.no_cache

    if args.use_async:
        if not ASYNC_AVAILABLE:
            print("[错误] 异步接口不可用（aiohttp 未安装）", file=sys.stderr)
            sys.exit(1)
        import asyncio
        async def run():
            return await async_search(
                args.query, args.topic, args.max_results,
                use_cache, args.api_key,
            )
        result = asyncio.run(run())
    else:
        result = search(args.query, args.topic, args.max_results, use_cache, args.api_key)

    result_text = _format_results_text(result.get("results", []))
    print(f"\n{'=' * 70}")
    print(f"[搜索结果]")
    print(result_text)
    print(f"[统计] 耗时: {result.get('search_time_ms', 0)} ms | "
          f"缓存: {'命中' if result.get('cached') else 'miss'} | "
          f"降级: {'是' if result.get('used_fallback') else '否'}")
    if result.get("error"):
        print(f"[错误] {result.get('error')}")
    print(f"{'=' * 70}")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n[保存] 结果已保存: {args.output}")

    sys.stdout.flush()


if __name__ == "__main__":
    main()
