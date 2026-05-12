"""
晨会图(LangGraph)模块

本模块使用LangGraph框架构建晨会工作流图,实现:
- 收集和初始化晨会参数
- 执行晨会分析工作流
- 使用StateGraph管理状态流转

工作流程:
START -> collect(收集参数) -> run(执行工作流) -> END
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ai_quant_api.services.ceo.morning_brief import run_morning_workflow


def build_graph():
    """
    构建晨会工作流图
    
    使用StateGraph构建包含以下节点的有向无环图:
    - collect: 收集和初始化晨会所需的参数
    - run: 执行晨会分析工作流
    
    Returns:
        编译后的LangGraph图对象
    """
    graph = StateGraph(dict)

    def collect(state: dict[str, Any]) -> dict[str, Any]:
        """
        收集节点:初始化晨会参数
        
        设置默认参数值:
        - industry_level: 行业层级(默认2)
        - top_n_industries: 选用的行业数量(默认5)
        - top_n_stocks: 每个行业选用的股票数量(默认5)
        - lookback_days: 回溯天数(默认90)
        - sample_stocks: 采样股票数(默认20)
        - messages: 消息列表(默认空)
        - trigger_time: 触发时间(默认None)
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态字典
        """
        payload = dict(state)
        # 设置默认行业层级
        if "industry_level" not in payload:
            payload["industry_level"] = 2
        # 设置默认行业数量
        if "top_n_industries" not in payload:
            payload["top_n_industries"] = 5
        # 设置默认股票数量
        if "top_n_stocks" not in payload:
            payload["top_n_stocks"] = 5
        # 设置默认回溯天数
        if "lookback_days" not in payload:
            payload["lookback_days"] = 90
        # 设置默认采样股票数
        if "sample_stocks" not in payload:
            payload["sample_stocks"] = 20
        # 初始化消息列表
        if "messages" not in payload:
            payload["messages"] = []
        # 设置触发时间
        if "trigger_time" not in payload:
            payload["trigger_time"] = None
        # 预留:处理输入日期的逻辑
        if "input" in payload and "end_date" not in payload:
            pass
        return payload

    def run(state: dict[str, Any]) -> dict[str, Any]:
        """
        执行节点:运行晨会工作流
        
        调用晨会服务执行实际的晨会分析工作流
        
        Args:
            state: 当前状态字典
            
        Returns:
            工作流执行结果
        """
        return run_morning_workflow(state)

    # 添加节点到图中
    graph.add_node("collect", collect)
    graph.add_node("run", run)
    
    # 设置节点连接边
    graph.add_edge(START, "collect")  # 起始节点指向collect
    graph.add_edge("collect", "run")  # collect指向run
    graph.add_edge("run", END)  # run指向结束节点
    
    return graph.compile()
