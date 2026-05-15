from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from langchain_community.chat_models.tongyi import ChatTongyi

from llm.tools import list_tool_defs, run_tool


def _require_dashscope_key() -> None:
    if not (os.getenv("DASHSCOPE_API_KEY") or "").strip():
        raise RuntimeError("缺少环境变量 DASHSCOPE_API_KEY")


def _tool_catalog() -> dict[str, dict[str, Any]]:
    items = list_tool_defs()
    out: dict[str, dict[str, Any]] = {}
    for it in items:
        name = str(it.get("name") or "").strip()
        if not name:
            continue
        out[name] = dict(it)
    return out


def _compact_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


@dataclass
class DeepAgentResult:
    text: str
    steps: list[dict[str, Any]]


_MEM: dict[str, list[dict[str, str]]] = {}


def _get_thread(thread_id: str) -> list[dict[str, str]]:
    key = (thread_id or "default").strip() or "default"
    if key not in _MEM:
        _MEM[key] = []
    return _MEM[key]


def _trim_thread(msgs: list[dict[str, str]], *, max_messages: int = 20) -> None:
    if len(msgs) > max_messages:
        del msgs[:-max_messages]


def _system_prompt(tool_catalog: dict[str, dict[str, Any]]) -> str:
    tool_lines = []
    for name, it in tool_catalog.items():
        title = str(it.get("title") or "")
        desc = str(it.get("description") or "")
        tool_lines.append(f"- {name} | {title} | {desc}")
    tools_text = "\n".join(tool_lines)

    today_str = datetime.now().strftime("%Y年%m月%d日")
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_str = weekday_names[datetime.now().weekday()]

    return (
        f"你是 AI 量化投资助手，负责数据查询、研报分析、舆情监控、策略回测与交易辅助。\n"
        "\n"
        f"=== 重要: 当前时间 ===\n"
        f"今天是 {today_str} {weekday_str}。\n"
        f"你必须以此日期为基准来理解时间:\n"
        f"- 2024年及之前的数据属于历史数据\n"
        f"- 2025年的数据属于近期已发生的数据（不是未来）\n"
        f"- 在撰写研报时，请确保时间表述准确，不要把已经过去的时间当作未来\n"
        "\n"
        "=== 可用工具 ===\n"
        f"{tools_text}\n"
        "\n"
        "=== 常用股票代码 ===\n"
        "- 中芯国际 688981.SH\n"
        "- 贵州茅台 600519.SH\n"
        "- 五粮液 000858.SZ\n"
        "- 比亚迪 002594.SZ\n"
        "- 宁德时代 300750.SZ\n"
        "\n"
        "=== 核心工作方法论 ===\n"
        "当用户要求写研报、深度分析、五步法分析时，你应该自己做研究和分析。\n"
        "核心方法论: 国泰君安\"五步法\"（信息差 -> 逻辑差 -> 预期差 -> 催化剂 -> 结论+风险闭环）。\n"
        "\n"
        "--- 第一阶段: 规划 ---\n"
        "先思考再行动:\n"
        "1. 识别分析对象（个股/行业/事件）\n"
        "2. 判断属于哪种研报场景: 个股深度 / 季报速评 / 行业比较 / 事件驱动 / 财务异常\n"
        "3. 列出五步法每一步需要搜集什么信息\n"
        "4. 规划搜索序列（先搜什么、再搜什么）\n"
        "\n"
        "--- 第二阶段: 迭代式信息收集 ---\n"
        "以 web_search 为主要信息来源，通过多轮搜索逐步积累分析素材:\n"
        "- 第一轮: 搜索公司/行业的基本面概况\n"
        "- 分析结果: 从搜索结果中发现新线索、新问题\n"
        "- 第二轮: 针对发现的线索追加搜索（这是关键 -- 不要一次搜完就停）\n"
        "- 继续迭代: 直到五步法每一步都有足够的数据支撑\n"
        "\n"
        "辅助信息来源（按需使用）:\n"
        "- query_pdf: 本地 RAG，精确的财报附注数据（仅当有该股票本地数据时）\n"
        "- financial_analysis: 结构化的 ROE/毛利率/负债率等趋势\n"
        "- stock_price: 实时行情和 K 线走势\n"
        "- compare_reports_period / compare_reports_company: 跨期或跨公司对比\n"
        "- strategy_backtest: 技术指标信号和胜率\n"
        "\n"
        "--- 第三阶段: 五步法分析与输出 ---\n"
        "收集够信息后，按五步法框架输出 Markdown 格式研报。\n"
        "\n"
        "五步法思考链（每步必须回答核心问题）:\n"
        "\n"
        "Step 1 信息差 -- 市场还不知道/忽视了什么？\n"
        "  重点: 财报附注中的隐藏数据、非经常性损益、新业务增长信号、现金流与利润的背离\n"
        "  输出: 3-5个被市场忽视的关键数据点，附具体数字\n"
        "\n"
        "Step 2 逻辑差 -- 市场的推理错在哪里？\n"
        "  重点: 识别市场的线性思维误区，构建正确的因果逻辑链\n"
        "  输出: 市场误读 vs 正确逻辑的对比\n"
        "\n"
        "Step 3 预期差 -- 一致预期 vs 实际偏离多大？\n"
        "  重点: 量化偏离幅度，判断是一次性还是可持续的\n"
        "  输出: 预期差对比表（指标/一致预期/我的预测/偏离幅度）\n"
        "\n"
        "Step 4 催化剂 -- 什么事件会引爆重估？\n"
        "  重点: 短期(1-3月)、中期(3-12月)催化剂时间轴 + 潜在风险催化\n"
        "  输出: 按时间排序的催化剂清单\n"
        "\n"
        "Step 5 结论+风险闭环 -- 最终判断 + 哪里可能出错？\n"
        "  重点: 明确投资评级，关键假设\n"
        "  风险闭环: 必须指出\"哪个假设出错会导致整个结论崩塌\"\n"
        "  输出: 核心观点 + 投资逻辑 + 失效条件\n"
        "\n"
        "=== 五种研报场景 ===\n"
        "\n"
        "场景1 - 个股深度: web_search 公司基本面 -> 行业格局 -> 竞品对比 -> 券商评级 -> 近期事件\n"
        "场景2 - 季报速评: query_pdf 本地RAG优先(如有) + web_search 市场预期对比\n"
        "场景3 - 行业比较: web_search 各公司最新业绩 -> 估值对比 -> compare_reports_company\n"
        "场景4 - 事件驱动: web_search 政策/新闻 为主 -> 受益公司 -> 预期差分析\n"
        "场景5 - 财务异常: financial_analysis 定量 + query_pdf 附注深挖\n"
        "\n"
        "=== 输出协议 ===\n"
        "请严格按以下 JSON 协议输出（只输出 JSON，不要输出任何其它文字）：\n"
        "1) 调用工具：\n"
        '{"action":"tool","tool_name":"<name>","args":{...}}\n'
        "2) 最终回答：\n"
        '{"action":"final","text":"<answer>"}\n'
        "\n"
        "=== 规则 ===\n"
        "- 优先选择最匹配的工具；工具的 args 必须符合其 input_schema。\n"
        "- 如需执行脚本类技能，使用工具 skills.exec。\n"
        "- 最终回答必须是中文，并且不要输出表情符号。\n"
        "- 投资建议需附带风险提示。\n"
    )


def run_deepagent(user_input: str, *, thread_id: str = "default", max_steps: int = 6) -> DeepAgentResult:
    _require_dashscope_key()
    catalog = _tool_catalog()
    sys_prompt = _system_prompt(catalog)

    llm = ChatTongyi(model=os.environ.get("AI_QUANT_AGENT_MODEL", "qwen-plus"))

    thread = _get_thread(thread_id)
    thread.append({"role": "user", "content": user_input})
    _trim_thread(thread)

    steps: list[dict[str, Any]] = []

    def _invoke(messages: list[dict[str, str]]) -> str:
        res = llm.invoke([{"role": "system", "content": sys_prompt}, *messages])
        return str(getattr(res, "content", "") or "")

    working = list(thread)
    for _ in range(int(max_steps)):
        raw = _invoke(working)
        try:
            obj = json.loads(raw)
        except Exception:
            steps.append({"type": "final", "text": raw})
            thread.append({"role": "assistant", "content": raw})
            _trim_thread(thread)
            return DeepAgentResult(text=raw, steps=steps)

        action = str(obj.get("action") or "").strip()
        if action == "final":
            text = str(obj.get("text") or "").strip()
            steps.append({"type": "final", "text": text})
            thread.append({"role": "assistant", "content": text})
            _trim_thread(thread)
            return DeepAgentResult(text=text, steps=steps)

        if action != "tool":
            text = raw
            steps.append({"type": "final", "text": text})
            thread.append({"role": "assistant", "content": text})
            _trim_thread(thread)
            return DeepAgentResult(text=text, steps=steps)

        tool_name = str(obj.get("tool_name") or "").strip()
        args = obj.get("args") or {}
        if tool_name not in catalog:
            obs = {"error": f"unknown tool: {tool_name}", "known": sorted(catalog.keys())[:50]}
            steps.append({"type": "tool_error", "tool": tool_name, "args": args, "result": obs})
            working.append({"role": "assistant", "content": _compact_json(obj)})
            working.append({"role": "user", "content": "工具不存在，重新选择工具。"})
            continue

        if not isinstance(args, dict):
            args = {"value": args}

        try:
            tool_res = run_tool(tool_name, dict(args))
            steps.append({"type": "tool", "tool": tool_name, "args": args, "result": tool_res})
            working.append({"role": "assistant", "content": _compact_json(obj)})
            working.append({"role": "user", "content": "工具结果：" + _compact_json(tool_res)})
        except Exception as e:
            tool_res = {"error": f"{type(e).__name__}: {e}"}
            steps.append({"type": "tool_error", "tool": tool_name, "args": args, "result": tool_res})
            working.append({"role": "assistant", "content": _compact_json(obj)})
            working.append({"role": "user", "content": "工具报错：" + _compact_json(tool_res)})

    text = "已达到最大执行步数，仍未得到最终结论。请提供更明确的输入或缩小范围。"
    thread.append({"role": "assistant", "content": text})
    _trim_thread(thread)
    steps.append({"type": "final", "text": text})
    return DeepAgentResult(text=text, steps=steps)

