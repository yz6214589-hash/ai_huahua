"""
意图路由Agent模块

本模块负责分析用户输入并将其路由到适当的处理模块:
- 识别晨会相关请求,路由到morning_brief图流程
- 其他请求默认路由到量化助手工具

使用关键词匹配策略进行简单路由判断
"""

from __future__ import annotations

from typing import Any


def route_intent(user_input: str) -> dict[str, Any]:
    """
    根据用户输入路由到对应的处理模块
    
    路由策略:
    - 空输入: 返回none目标
    - 包含"晨会"关键词: 路由到morning_brief图流程
    - 其他情况: 默认路由到量化助手工具
    
    Args:
        user_input: 用户的输入文本
        
    Returns:
        包含目标模块和路由原因的字典
    """
    # 去除首尾空白字符
    text = user_input.strip()
    # 空输入直接返回none目标
    if not text:
        return {"target": "none", "reason": "empty_input"}
    # 检测晨会关键词,路由到晨会流程
    if "晨会" in text:
        return {"target": "graph:morning_brief", "reason": "matched_keyword"}
    # 默认路由到量化助手
    return {"target": "tool:quant_assistant", "reason": "default_route"}
