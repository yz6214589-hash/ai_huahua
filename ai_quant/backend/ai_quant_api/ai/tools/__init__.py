from __future__ import annotations

from typing import Any

from ai_quant_api.services.ceo.integration import trigger_morning
from ai_quant_api.services.charles.integration import get_summary
from ai_quant_api.services.ethan.integration import create_execution_task
from ai_quant_api.services.kris.integration import approve


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
    raise KeyError(f"unknown tool: {tool_name}")
