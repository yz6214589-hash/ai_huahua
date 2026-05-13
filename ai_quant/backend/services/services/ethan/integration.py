"""
Ethan 服务模块 - 执行任务管理服务

本模块提供以下核心功能：
- 执行任务创建：创建量化交易执行任务
- 执行任务查询：获取单个任务详情或任务列表
- 内存存储：使用内存存储管理任务状态

任务包含交易策略参数、执行步骤、市场影响模型参数等信息。
使用单例模式的内存存储（InMemoryStore）保存任务数据。
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from datetime import datetime, timezone

from services.ethan.models import ExecutionTask, ExecutionTaskCreate
from services.ethan.store import InMemoryStore

# 单例模式的内存存储实例
_STORE = None


def _get_store():
    """
    获取内存存储实例
    
    使用单例模式，确保整个应用只有一个存储实例。
    
    Returns:
        InMemoryStore: 内存存储实例
    """
    global _STORE
    if _STORE is not None:
        return _STORE
    _STORE = InMemoryStore()
    return _STORE


def _now_iso() -> str:
    """
    获取当前UTC时间的ISO格式字符串
    
    Returns:
        str: ISO格式的当前时间字符串
    """
    return datetime.now(timezone.utc).isoformat()


def get_status() -> dict[str, Any]:
    """
    获取 Ethan 服务状态信息
    
    Returns:
        dict[str, Any]: 服务状态，包括数据源名称和可用功能
    """
    return {"source": "ethan", "status": "ready", "features": ["tasks"], "mode": "embedded"}


def create_execution_task(payload: dict[str, Any]) -> dict[str, Any]:
    """
    创建执行任务
    
    根据传入参数创建一个新的执行任务，并保存到内存存储中。
    
    Args:
        payload: 任务创建参数，包含symbol、side、total_qty等字段
    
    Returns:
        dict[str, Any]: 创建的任务详情
    """
    # 解析并验证输入参数
    req = ExecutionTaskCreate(**payload)
    # 默认平均每日成交量为200万
    adv = float(req.adv or 2_000_000)
    # 创建任务对象
    task = ExecutionTask(
        id=uuid4().hex,
        symbol=req.symbol,
        side=req.side,
        total_qty=req.total_qty,
        num_steps=req.num_steps,
        strategy=req.strategy,
        rl_model_path=req.rl_model_path,
        impact_eta=req.impact_eta,
        impact_gamma=req.impact_gamma,
        adv=adv,
        constraints=req.constraints,
        status="draft",
        created_at=_now_iso(),
    )
    # 保存到内存存储
    store = _get_store()
    store.put_task(task)
    return task.model_dump()


def list_execution_tasks() -> dict[str, Any]:
    """
    获取所有执行任务列表
    
    Returns:
        dict[str, Any]: 包含items（任务列表）的字典
    """
    store = _get_store()
    return {"items": [x.model_dump() for x in store.list_tasks()]}


def get_execution_task(task_id: str) -> dict[str, Any] | None:
    """
    获取指定执行任务的详情
    
    Args:
        task_id: 任务ID
    
    Returns:
        dict[str, Any] | None: 任务详情，如果不存在则返回None
    """
    store = _get_store()
    task = store.get_task(task_id)
    if not task:
        return None
    return {"task": task.model_dump()}
