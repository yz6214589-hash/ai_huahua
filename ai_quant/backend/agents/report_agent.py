from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _backend_root() -> Path:
    return BACKEND_ROOT


def _run_script(script_path: str, args: List[str], timeout: int = 300) -> str:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        result = subprocess.run(
            [sys.executable, script_path] + args,
            capture_output=True,
            cwd=str(_backend_root()),
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        output = (result.stdout or "").strip()
        if result.returncode != 0 and result.stderr:
            output += "\n[stderr] " + result.stderr.strip()
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: script timed out"
    except Exception as e:
        return "Error: " + str(e)


SYSTEM_PROMPT_TEMPLATE = [
    "你是 Charles，一位专业的 AI 投研情报官。你为投资者提供深度研究分析服务。",
    "",
    "=== 重要: 当前时间 ===",
    "",
    "=== 可用工具 ===",
    "- web_search: 联网搜索最新市场信息、新闻、公告",
    "- query_pdf: 从本地 PDF 研报/财报知识库检索（RAG）",
    "- stock_price: 获取 A 股实时 K 线数据",
    "- financial_analysis: 分析财务指标趋势（ROE/毛利率/负债率等）",
    "- compare_reports_period: 同一公司跨期纵向对比",
    "- compare_reports_company: 不同公司横向对比",
    "- sentiment_analysis: 舆情情绪分析",
    "",
    "=== 研报撰写策略 ===",
    "",
    "核心方法论: 国泰君安五步法（信息差 -> 逻辑差 -> 预期差 -> 催化剂 -> 结论+风险闭环）。",
    "",
    "--- 第一阶段: 规划 ---",
    "先思考再行动，识别分析对象，列出五步法每一步需要搜集什么信息。",
    "",
    "--- 第二阶段: 迭代式信息收集 ---",
    "以 web_search 为主要信息来源，通过多轮搜索逐步积累分析素材，不要一次搜完就停。",
    "",
    "--- 第三阶段: 五步法分析与输出 ---",
    "收集够信息后，按五步法框架直接输出 Markdown 格式研报。",
    "",
    "Step 1 信息差 -- 市场还不知道/忽视了什么？",
    "Step 2 逻辑差 -- 市场的推理错在哪里？",
    "Step 3 预期差 -- 一致预期 vs 实际偏离多大？",
    "Step 4 催化剂 -- 什么事件会引爆重估？",
    "Step 5 结论+风险闭环 -- 最终判断 + 哪里可能出错？",
    "",
    "=== 输出格式 ===",
    "请直接输出 Markdown 格式研报正文，不要输出任何 JSON 或解释性文字。",
]


TOOL_SCRIPT_MAP = {
    "web_search": ("web-search-qwen/scripts/search_market.py", ["--query", "--type"]),
    "web_search_universal": ("web-search-universal/scripts/search.py", ["--query", "--topic", "--max-results"]),
    "query_pdf": ("read-pdf/scripts/query_report.py", ["--query", "--stock"]),
    "stock_price": ("stock-price/scripts/get_kline.py", ["code", "period", "count"]),
    "financial_analysis": ("financial-analysis/scripts/ratio_analysis.py", ["--stock", "--years"]),
    "compare_reports_period": ("compare-reports/scripts/cross_period.py", ["--stock", "--topics"]),
    "compare_reports_company": ("compare-reports/scripts/cross_company.py", ["--stocks", "--topic"]),
    "sentiment_analysis": ("sentiment-analysis/scripts/sentiment_scorer.py", ["--query", "--source"]),
}


@dataclass
class ReportAgentResult:
    text: str
    mode: str
    tools_used: List[str] = field(default_factory=list)
    error: str = None


def _exec_tool(tool_name: str, args: Dict[str, Any]) -> str:
    if tool_name not in TOOL_SCRIPT_MAP:
        return "Error: unknown tool '" + tool_name + "'"
    rel_script, param_keys = TOOL_SCRIPT_MAP[tool_name]
    script = str((_backend_root() / "llm" / "skills" / rel_script).resolve())
    cmd_args = []
    for k in param_keys:
        v = args.get(k)
        if v is not None:
            if isinstance(v, bool):
                v = "true" if v else "false"
            cmd_args.append(str(v))
    return _run_script(script, cmd_args)


def _invoke_llm(system_prompt: str, user_prompt: str, model: str) -> str:
    from langchain_community.chat_models.tongyi import ChatTongyi
    llm = ChatTongyi(model=model)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        res = llm.invoke(messages)
        return str(getattr(res, "content", "") or "")
    except Exception as e:
        return "LLM 调用失败: " + type(e).__name__ + ": " + str(e)


def _extract_final_markdown(raw: str) -> str:
    raw = raw.strip()
    B3 = chr(96) * 3
    for marker in (B3 + "markdown", B3 + "md", B3):
        if raw.startswith(marker):
            end = raw.find(B3, len(marker))
            if end != -1:
                return raw[len(marker):end].strip()
    return raw


def run_report_agent(
    stock_codes: List[str],
    stock_names: List[str],
    mode: str = "qwen",
    use_rag: bool = False,
    model: str = None,
    max_iterations: int = 4,
) -> ReportAgentResult:
    """
    运行研报 Agent，返回 Markdown 研报文本。

    Args:
        stock_codes: 股票代码列表
        stock_names: 股票名称列表
        mode: 生成模式 - qwen / qwen_with_rag / deepseek_with_web
        use_rag: 是否启用本地 RAG
        model: LLM 模型名，默认根据 mode 选择
        max_iterations: 最大搜索迭代轮数（默认4）

    Returns:
        ReportAgentResult(text=markdown, mode=..., tools_used=[...], error=...)
    """
    if model is None:
        if mode == "deepseek_with_web":
            model = "deepseek-chat"
        else:
            model = os.getenv("CHARLES_MODEL", "qwen-plus")

    actual_mode = "qwen_with_rag" if (use_rag and mode == "qwen") else mode

    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    today_str = datetime.now().strftime("%Y年%m月%d日")
    weekday_str = weekday_names[datetime.now().weekday()]

    system_prompt_parts = list(SYSTEM_PROMPT_TEMPLATE)
    system_prompt_parts[2] = "今天是 " + today_str + " " + weekday_str + "。"
    system_prompt = "\n".join(system_prompt_parts)

    stock_name = (stock_names or stock_codes)[0]
    stock_code = stock_codes[0]
    user_prompt = "请对以下股票进行深度研报分析（五步法）: " + stock_name + "(" + stock_code + ")"

    tools_used = []
    iteration = 0
    history = [{"role": "user", "content": user_prompt}]

    while iteration < max_iterations:
        iteration += 1
        raw = _invoke_llm(system_prompt, "\n".join([m["content"] for m in history]), model)
        markdown = _extract_final_markdown(raw)

        if markdown and len(markdown) > 200:
            return ReportAgentResult(text=markdown, mode=mode, tools_used=tools_used)

        tool_calls = re.findall(r"\{[^}]+\}", raw)
        if not tool_calls:
            if markdown:
                return ReportAgentResult(text=markdown, mode=mode, tools_used=tools_used)
            return ReportAgentResult(
                text=markdown or raw or "(no output)",
                mode=mode,
                tools_used=tools_used,
            )

        tool_results = []
        for call_str in tool_calls:
            try:
                call = json.loads(call_str)
                tool_name = str(call.get("tool") or call.get("tool_name") or "")
                args = call.get("args") or call.get("arguments") or {}
                if not tool_name:
                    continue
                result = _exec_tool(tool_name, args)
                tool_results.append("[" + tool_name + "] " + result)
                tools_used.append(tool_name)
            except Exception:
                tool_results.append("[parse error] " + call_str)

        history.append({
            "role": "user",
            "content": "请继续。以下是工具执行结果:\n" + "\n".join(tool_results),
        })

    final_raw = _invoke_llm(system_prompt, "\n".join([m["content"] for m in history]), model)
    return ReportAgentResult(
        text=_extract_final_markdown(final_raw) or final_raw,
        mode=mode,
        tools_used=tools_used,
    )
