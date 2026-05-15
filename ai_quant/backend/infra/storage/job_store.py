"""
Agent运行记录存储模块

本模块负责管理Agent执行运行的历史记录,提供:
- 运行记录的添加和查询
- 内存中的运行历史存储(最多保留50条)
- 线程安全的并发访问控制

主要用于追踪和审计Agent的执行历史
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from threading import Lock


@dataclass
class AgentRunRecord:
    """
    Agent运行记录数据类
    
    存储单个Agent执行运行的信息:
    - run_id: 运行的唯一标识符
    - input: 运行的输入内容
    - route: 路由到的目标或处理路径
    - created_at: 运行创建时间
    """
    run_id: str
    input: str
    route: str
    created_at: str


# 内存中的运行记录列表,最多保留50条
_RUNS: list[AgentRunRecord] = []
# 线程锁,保证并发访问_RUNS时的数据一致性
_LOCK = Lock()


def append_run(record: AgentRunRecord) -> None:
    """
    添加新的运行记录到历史列表
    
    新记录插入到列表开头(最新优先),
    如果列表超过50条则删除最旧的记录
    
    Args:
        record: 要添加的运行记录
    """
    with _LOCK:
        # 插入到列表开头
        _RUNS.insert(0, record)
        # 保持列表长度不超过50条
        del _RUNS[50:]


def list_runs() -> list[dict[str, str]]:
    """
    获取所有运行记录的列表
    
    Returns:
        运行记录列表,每条记录为字典格式
    """
    with _LOCK:
        return [asdict(x) for x in _RUNS]


def now_iso() -> str:
    """
    获取当前时间的ISO格式字符串
    
    Returns:
        当前时间的ISO 8601格式字符串,精确到秒
    """
    return datetime.now().isoformat(timespec="seconds")
