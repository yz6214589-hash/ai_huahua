from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Side(str, Enum):
    """交易方向枚举"""
    buy = "buy"    # 买入
    sell = "sell"  # 卖出


class ExecutionTaskCreate(BaseModel):
    """创建执行任务的请求模型"""
    symbol: str                                                    # 股票代码
    side: Side                                                     # 交易方向
    total_qty: int = Field(ge=100)                                 # 总委托数量，最小100股


class ExecutionTask(BaseModel):
    """执行任务的完整数据模型"""
    model_config = ConfigDict(protected_namespaces=())

    id: str                                                        # 任务唯一标识UUID
    symbol: str                                                    # 股票代码
    side: Side                                                     # 交易方向
    total_qty: int                                                 # 总委托数量
    status: Literal["draft", "running", "stopped", "finished", "failed"]  # 任务状态
    created_at: str                                                # 创建时间（ISO格式）
    started_at: str | None = None                                  # 开始执行时间
    finished_at: str | None = None                                 # 完成时间
    error: str | None = None                                       # 错误信息（仅failed状态有值）
    meta: dict[str, Any] = Field(default_factory=dict)             # 扩展元数据
