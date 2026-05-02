from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool
from langchain_core.tools import StructuredTool

from ..reports.llm import build_chat_model
from ..reports.models import ReportModel
from .tools import (
    event_detector,
    market_fear_index,
    news_fetcher,
    polymarket_monitor,
    query_pdf,
    require_dashscope_key,
    sentiment_scorer,
)


def build_assistant_instructions() -> str:
    today_str = datetime.now().strftime("%Y年%m月%d日")
    return f"""你是 Charles，对话式投研情报官。今天是 {today_str}。你的任务是回答投资相关问题，并在需要时调用工具来获取证据。

通用要求：
1. 先判断用户意图属于哪类场景：宏观+舆情联动 / 个股舆情 / 重大事件 / 全球情绪 / 全链路决策。
2. 工具输出往往包含 JSON 预览或输出文件路径，必须从中提炼可读结论。
3. 输出必须包含：结论摘要、关键证据（指标/事件/情绪统计）、仓位建议或操作策略、风险提示。

场景 1：宏观风险 + A股舆情联动
- 必须依次调用：market_fear_index -> polymarket_monitor -> news_fetcher(热点关键词) -> sentiment_scorer。
- 最后综合给出：仓位区间建议（0~100%）与分步策略（例如分批/止损/关注触发事件）。

场景 2：个股舆情（如比亚迪 002594）
- 调用：news_fetcher(stock=002594, days=7) -> sentiment_scorer(news_file)。
- 输出：整体情绪、正负面占比、风险/机会提示、操作建议。

场景 3：A股重大事件检测（资产重组/回购等）
- 调用：news_fetcher(keywords=资产重组,回购, days=3) -> event_detector(news_file)。
- 输出：事件数量、利好/利空判断、标的推荐、后续深挖入口（可建议创建研报任务）。

场景 4：全球市场情绪与加仓判断
- 调用：market_fear_index。
- 输出：综合恐慌/贪婪指数、关键指标解读、短期与中长期建议。

场景 5：全链路投资决策（deep 模式）
- 依次调用：market_fear_index -> polymarket_monitor -> news_fetcher(根据用户关注事件/关键词) -> event_detector(必要时) -> query_pdf(如有股票且用户要求财报证据)。
- 最后必须调用 create_report_task 创建研报任务，并在结论中给出 task_id 与查看链接提示。
"""


def _wrap_tool(fn: Callable[..., str], emit: Callable[[dict[str, Any]], None]) -> BaseTool:
    name = fn.name if hasattr(fn, "name") else fn.__name__
    description = fn.description if hasattr(fn, "description") else (fn.__doc__ or "")

    def _call(**kwargs: Any) -> str:
        emit({"type": "tool_start", "name": name, "args": kwargs})
        try:
            out = fn.invoke(kwargs) if hasattr(fn, "invoke") else fn(**kwargs)
            emit({"type": "tool_end", "name": name, "status": "ok", "output": out})
            return out
        except Exception as e:
            emit({"type": "tool_end", "name": name, "status": "error", "output": f"{type(e).__name__}: {e}"})
            raise

    return StructuredTool.from_function(_call, name=name, description=description)


def build_assistant_agent(*, emit: Callable[[dict[str, Any]], None], create_report_task_tool: BaseTool) -> Any:
    require_dashscope_key()
    llm = build_chat_model(ReportModel.qwen_max)
    tools = [
        _wrap_tool(market_fear_index, emit),
        _wrap_tool(polymarket_monitor, emit),
        _wrap_tool(news_fetcher, emit),
        _wrap_tool(sentiment_scorer, emit),
        _wrap_tool(event_detector, emit),
        _wrap_tool(query_pdf, emit),
        _wrap_tool(create_report_task_tool, emit),
    ]
    return create_deep_agent(model=llm, tools=tools, instructions=build_assistant_instructions())


def parse_tool_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        return None
