from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.console import trigger_morning
from core.data import get_summary
from core.execution import create_execution_task
from core.risk import approve


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _skills_root() -> Path:
    return _backend_root() / "llm" / "skills"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _run_skill_script(script: str, args: list[str] | None = None, *, timeout: int = 300) -> str:
    base = _backend_root()
    rel = f"llm/skills/{script.lstrip('/')}"
    script_path = (base / rel).resolve()
    if base not in script_path.parents:
        raise ValueError("script 路径不允许跳出项目目录")
    if not script_path.exists():
        raise FileNotFoundError(f"script 不存在: {script}")
    if script_path.suffix.lower() != ".py":
        raise ValueError("仅允许执行 .py 脚本")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend([str(x) for x in args])

    result = subprocess.run(
        cmd,
        capture_output=True,
        cwd=str(base),
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0 and err:
        out = (out + "\n" + err).strip()
    return out or "(no output)"


_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "data.query_summary",
        "title": "查询数据汇总",
        "description": "读取 Charles 数据汇总指标",
        "target": "charles.summary",
        "tags": ["data", "charles"],
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "execution.create_task",
        "title": "创建执行任务",
        "description": "创建 Ethan 执行任务",
        "target": "ethan.execution",
        "tags": ["execution", "ethan"],
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "side": {"type": "string"},
                "total_qty": {"type": "number"},
                "num_steps": {"type": "number"},
                "strategy": {"type": "string"},
                "adv": {"type": "number"},
            },
            "required": ["symbol", "side", "total_qty", "num_steps", "strategy"],
        },
    },
    {
        "name": "risk.approve_order",
        "title": "风控审批",
        "description": "调用 Kris 审批交易指令",
        "target": "kris.approve",
        "tags": ["risk", "kris"],
        "input_schema": {
            "type": "object",
            "properties": {
                "order": {"type": "object"},
                "portfolio": {"type": "object"},
                "context": {"type": "object"},
            },
            "required": ["order", "portfolio"],
        },
    },
    {
        "name": "report.generate_morning",
        "title": "生成晨会简报",
        "description": "触发 CEO 晨会工作流并返回结果",
        "target": "ceo.morning_brief",
        "tags": ["report", "ceo", "langgraph"],
        "input_schema": {
            "type": "object",
            "properties": {
                "top_n_industries": {"type": "number"},
                "top_n_stocks": {"type": "number"},
                "sample_stocks": {"type": "number"},
                "lookback_days": {"type": "number"},
            },
            "required": [],
        },
    },
    {
        "name": "web_search",
        "title": "联网搜索",
        "description": "搜索网络获取最新市场新闻、政策、公司公告和分析报告",
        "target": "skills.web-search-qwen",
        "tags": ["research", "web"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词，如 贵州茅台 2025年年报 业绩"},
                "type": {"type": "string", "description": "搜索类型 - general(通用)/news(新闻)/stock(个股)/policy(政策)", "default": "general"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_search_universal",
        "title": "通用联网搜索（Tavily）",
        "description": "基于 Tavily SDK 的通用联网搜索，支持同步/异步两套接口，输出结构化 JSON（含标题、摘要、URL、发布时间）。Tavily Key 未配置时自动降级至 DuckDuckGo/Bing，适用于 Deepseek + 联网搜索等 Agent 场景",
        "target": "skills.web-search-universal",
        "tags": ["research", "web", "tavily"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询字符串，如 宁德时代 最新业绩 2026"},
                "topic": {"type": "string", "description": "搜索主题 - general(通用)/news(新闻)/finance(金融)", "default": "general"},
                "max_results": {"type": "number", "description": "最大返回结果数（默认5）", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_pdf",
        "title": "PDF研报查询",
        "description": "从本地 PDF 研报/财报知识库检索信息（RAG），支持页码溯源",
        "target": "skills.read-pdf",
        "tags": ["research", "pdf"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询问题，如 2024年营收和净利润数据"},
                "stock": {"type": "string", "description": "按股票代码过滤（如 600519），留空搜索全部"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "stock_price",
        "title": "获取股票K线",
        "description": "获取 A 股实时 K 线数据（通过 MiniQMT）",
        "target": "skills.stock-price",
        "tags": ["market", "price"],
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码，如 600519.SH、000001.SZ"},
                "period": {"type": "string", "description": "K线周期 - 1d(日线)/1w(周线)/1m(1分钟)/5m/15m/30m/1h", "default": "1d"},
                "count": {"type": "number", "description": "获取条数（默认20）", "default": 20},
            },
            "required": ["code"],
        },
    },
    {
        "name": "financial_analysis",
        "title": "财务指标分析",
        "description": "分析上市公司核心财务指标趋势（毛利率/ROE/负债率等），支持同行业横向对比",
        "target": "skills.financial-analysis",
        "tags": ["research", "financial"],
        "input_schema": {
            "type": "object",
            "properties": {
                "stock": {"type": "string", "description": "股票代码，如 600519"},
                "years": {"type": "number", "description": "分析年数（默认5年）", "default": 5},
            },
            "required": ["stock"],
        },
    },
    {
        "name": "compare_reports_period",
        "title": "跨期对比分析",
        "description": "同一公司不同时期（季度/年度）的纵向对比分析",
        "target": "skills.compare-reports",
        "tags": ["research", "compare"],
        "input_schema": {
            "type": "object",
            "properties": {
                "stock": {"type": "string", "description": "股票代码，如 688981"},
                "topics": {"type": "string", "description": "对比维度（逗号分隔），如 营收,净利润,毛利率", "default": "营收,净利润,毛利率,经营情况"},
            },
            "required": ["stock"],
        },
    },
    {
        "name": "compare_reports_company",
        "title": "公司对比分析",
        "description": "不同公司之间的横向对比分析",
        "target": "skills.compare-reports",
        "tags": ["research", "compare"],
        "input_schema": {
            "type": "object",
            "properties": {
                "stocks": {"type": "string", "description": "股票代码列表（逗号分隔），如 688981,600519"},
                "topic": {"type": "string", "description": "对比主题", "default": "经营状况和盈利能力"},
            },
            "required": ["stocks"],
        },
    },
    {
        "name": "sentiment_analysis",
        "title": "舆情分析",
        "description": "分析市场舆情情绪，包括新闻情感评分、市场恐惧指数等",
        "target": "skills.sentiment-analysis",
        "tags": ["market", "sentiment"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询关键词"},
                "source": {"type": "string", "description": "数据源 - news/macro/polymarket", "default": "news"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "strategy_backtest",
        "title": "策略回测",
        "description": "运行策略回测获取信号和历史胜率",
        "target": "skills.strategy-backtest",
        "tags": ["strategy", "backtest"],
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "股票代码"},
                "strategy": {"type": "string", "description": "策略名称，如 macd/rsi/talib", "default": "macd"},
                "count": {"type": "number", "description": "K线数量", "default": 250},
            },
            "required": ["code"],
        },
    },
    {
        "name": "trade_order",
        "title": "交易下单",
        "description": "通过 MiniQMT 进行交易下单或查询账户",
        "target": "skills.trade-order",
        "tags": ["trading", "order"],
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作类型 - place_order/query_account"},
                "symbol": {"type": "string", "description": "股票代码"},
                "price": {"type": "number", "description": "价格（市价单填0）"},
                "qty": {"type": "number", "description": "数量"},
                "side": {"type": "string", "description": "买卖方向 - buy/sell"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "write_report",
        "title": "生成研报",
        "description": "按照五步法框架生成深度投资研报",
        "target": "skills.write-report",
        "tags": ["research", "report"],
        "input_schema": {
            "type": "object",
            "properties": {
                "stock": {"type": "string", "description": "股票代码"},
                "template": {"type": "string", "description": "研报模板 - five_step/custom", "default": "five_step"},
            },
            "required": ["stock"],
        },
    },
    {
        "name": "skills.exec",
        "title": "执行技能脚本",
        "description": "执行 backend/skills 下的脚本（script 为相对 skills 的路径）",
        "target": "skills.exec",
        "tags": ["skills"],
        "input_schema": {
            "type": "object",
            "properties": {
                "script": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
                "timeout": {"type": "number"},
            },
            "required": ["script"],
        },
    },
    {
        "name": "skills.read_doc",
        "title": "读取技能文档",
        "description": "读取某个技能目录下的 SKILL.md",
        "target": "skills.read_doc",
        "tags": ["skills"],
        "input_schema": {
            "type": "object",
            "properties": {"skill": {"type": "string"}},
            "required": ["skill"],
        },
    },
]


def list_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def run_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "data.query_summary":
        return get_summary()
    if tool_name == "execution.create_task":
        return {"task": create_execution_task(payload)}
    if tool_name == "risk.approve_order":
        return approve(payload)
    if tool_name == "report.generate_morning":
        return trigger_morning(payload)
    if tool_name == "web_search":
        query = str(payload.get("query") or "")
        search_type = str(payload.get("type") or "general")
        script = f"web-search-qwen/scripts/search_market.py --query {query} --type {search_type}"
        return {"script": script, "output": _run_skill_script(script, timeout=120)}
    if tool_name == "web_search_universal":
        query = str(payload.get("query") or "")
        topic = str(payload.get("topic") or "general")
        max_results = int(payload.get("max_results") or 5)
        script = (
            f"web-search-universal/scripts/search.py --query {query} "
            f"--topic {topic} --max-results {max_results}"
        )
        return {"script": script, "output": _run_skill_script(script, timeout=120)}
    if tool_name == "query_pdf":
        query = str(payload.get("query") or "")
        stock = str(payload.get("stock") or "")
        script = f"read-pdf/scripts/query_report.py --query {query}"
        if stock:
            script += f" --stock {stock}"
        return {"script": script, "output": _run_skill_script(script, timeout=120)}
    if tool_name == "stock_price":
        code = str(payload.get("code") or "")
        period = str(payload.get("period") or "1d")
        count = int(payload.get("count") or 20)
        script = f"stock-price/scripts/get_kline.py {code} {period} {count}"
        return {"script": script, "output": _run_skill_script(script, timeout=60)}
    if tool_name == "financial_analysis":
        stock = str(payload.get("stock") or "")
        years = int(payload.get("years") or 5)
        script = f"financial-analysis/scripts/ratio_analysis.py --stock {stock} --years {years}"
        return {"script": script, "output": _run_skill_script(script, timeout=120)}
    if tool_name == "compare_reports_period":
        stock = str(payload.get("stock") or "")
        topics = str(payload.get("topics") or "营收,净利润,毛利率,经营情况")
        script = f"compare-reports/scripts/cross_period.py --stock {stock} --topics {topics}"
        return {"script": script, "output": _run_skill_script(script, timeout=120)}
    if tool_name == "compare_reports_company":
        stocks = str(payload.get("stocks") or "")
        topic = str(payload.get("topic") or "经营状况和盈利能力")
        script = f"compare-reports/scripts/cross_company.py --stocks {stocks} --topic {topic}"
        return {"script": script, "output": _run_skill_script(script, timeout=120)}
    if tool_name == "sentiment_analysis":
        query = str(payload.get("query") or "")
        source = str(payload.get("source") or "news")
        script = f"sentiment-analysis/scripts/sentiment_scorer.py --query {query} --source {source}"
        return {"script": script, "output": _run_skill_script(script, timeout=120)}
    if tool_name == "strategy_backtest":
        code = str(payload.get("code") or "")
        strategy = str(payload.get("strategy") or "macd")
        count = int(payload.get("count") or 250)
        script = f"strategy-backtest/scripts/run_backtest.py --code {code} --strategy {strategy} --count {count}"
        return {"script": script, "output": _run_skill_script(script, timeout=180)}
    if tool_name == "trade_order":
        action = str(payload.get("action") or "")
        if action == "place_order":
            symbol = str(payload.get("symbol") or "")
            price = float(payload.get("price") or 0)
            qty = int(payload.get("qty") or 0)
            side = str(payload.get("side") or "buy")
            script = f"trade-order/scripts/place_order.py --symbol {symbol} --price {price} --qty {qty} --side {side}"
        elif action == "query_account":
            script = "trade-order/scripts/query_account.py"
        else:
            raise ValueError(f"未知的交易操作: {action}")
        return {"script": script, "output": _run_skill_script(script, timeout=60)}
    if tool_name == "write_report":
        stock = str(payload.get("stock") or "")
        template = str(payload.get("template") or "five_step")
        script = f"write-report/scripts/report_generator.py --stock {stock} --template {template}"
        return {"script": script, "output": _run_skill_script(script, timeout=300)}
    if tool_name == "skills.exec":
        script = str(payload.get("script") or "").strip()
        if not script:
            raise ValueError("script 不能为空")
        args = payload.get("args")
        args_list = [str(x) for x in (args or [])]
        timeout = int(payload.get("timeout") or 300)
        return {"script": script, "output": _run_skill_script(script, args=args_list, timeout=timeout)}
    if tool_name == "skills.read_doc":
        skill = str(payload.get("skill") or "").strip()
        if not skill:
            raise ValueError("skill 不能为空")
        p = (_skills_root() / skill / "SKILL.md").resolve()
        if _skills_root() not in p.parents:
            raise ValueError("skill 不合法")
        if not p.exists():
            raise FileNotFoundError(f"SKILL.md 不存在: {skill}")
        return {"skill": skill, "content": _read_text(p)}
    raise KeyError(f"unknown tool: {tool_name}")
