from __future__ import annotations

from datetime import datetime

from .llm import build_chat_model
from .models import ReportModel
from .tools import rag_search, web_search


def build_report_agents(*, root_dir: str, model: ReportModel):
    from deepagents import create_deep_agent

    today_str = datetime.now().strftime("%Y年%m月%d日")

    tools = [web_search, rag_search]
    llm = build_chat_model(model)

    planner = create_deep_agent(
        model=llm,
        instructions=f"你是投研规划助手。今天是 {today_str}。输出 JSON，字段：web_queries(list), rag_queries(list), outline(str)。只输出 JSON。",
        tools=tools,
    )

    researcher = create_deep_agent(
        model=llm,
        instructions=f"你是投研研究员。今天是 {today_str}。你必须优先调用 web_search 和 rag_search 获取证据，再汇总为要点清单，标注来源与时间。",
        tools=tools,
    )

    writer = create_deep_agent(
        model=llm,
        instructions=f"你是研报写作助手。今天是 {today_str}。请按五步法输出 Markdown 研报，包含风险提示，并把引用信息写在要点后括号内。",
        tools=tools,
    )

    reviewer = create_deep_agent(
        model=llm,
        instructions=f"你是研报审校助手。今天是 {today_str}。检查时间表述、事实引用与风险提示，输出最终 Markdown（如需修改，直接给出修订后的全文）。",
        tools=tools,
    )

    return planner, researcher, writer, reviewer
