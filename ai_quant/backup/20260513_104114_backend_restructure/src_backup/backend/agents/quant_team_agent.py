"""
量化团队Agent模块

本模块是量化团队AI助手的主入口,负责:
- 处理用户输入的量化分析任务
- 返回任务确认信息和可用的模块列表

团队成员包括:
- charles: 负责技术分析
- zoe: 负责基本面分析
- ethan: 负责量化策略
- kris: 负责风险控制
- ceo: 负责统筹协调
"""

from __future__ import annotations

from typing import Any, Optional


def run_quant_assistant(
    user_input: str,
    run_id: Optional[str] = None,
    route: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    运行量化助手处理用户输入

    接收用户的量化分析任务请求,返回任务确认信息和
    将参与处理该任务的团队模块列表

    Args:
        user_input: 用户的输入内容或任务描述
        run_id: 运行ID (可选)
        route: 路由信息 (可选)

    Returns:
        包含任务确认信息和团队模块列表的字典
    """
    text = user_input.strip().lower()

    if "数据" in text or "汇总" in text or "概览" in text:
        from src.backend..data import get_summary
        try:
            summary = get_summary()
            return {
                "message": f"已接收任务：{user_input}",
                "modules": ["charles"],
                "route_reason": "数据查询类请求",
                "result": summary,
            }
        except Exception as e:
            return {
                "message": f"数据查询失败：{e}",
                "modules": ["charles"],
                "error": str(e),
            }

    if "执行" in text or "下单" in text or "买入" in text or "卖出" in text:
        return {
            "message": f"已接收交易执行请求：{user_input}",
            "modules": ["ethan", "kris"],
            "route_reason": "交易执行请求",
            "hint": "请使用策略分析或风控审批页面执行交易",
        }

    if "风控" in text or "审批" in text or "风险" in text:
        return {
            "message": f"已接收风控请求：{user_input}",
            "modules": ["kris"],
            "route_reason": "风控审批类请求",
            "hint": "请使用风控审批页面提交指令",
        }

    if "报告" in text or "分析" in text or "个股" in text:
        return {
            "message": f"已接收分析请求：{user_input}",
            "modules": ["charles", "zoe"],
            "route_reason": "分析报告类请求",
            "hint": "请使用个股详情页面查看完整分析",
        }

    return {
        "message": f"已接收任务：{user_input}",
        "modules": ["charles", "zoe", "ethan", "kris", "ceo"],
        "route_reason": "通用请求",
        "hint": "您可以咨询：\n1. 数据汇总和概览\n2. 晨会简报生成\n3. 个股技术分析\n4. 量化策略分析\n5. 风控审批\n\n请告诉我您具体需要什么帮助？",
    }
