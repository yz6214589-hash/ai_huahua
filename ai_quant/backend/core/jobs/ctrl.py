"""
任务停止控制模块

提供运行中任务的停止信号机制，支持向指定 run_id 发送停止信号，
任务在下一次检查点时检测信号并自我终止。

线程安全：使用 threading.Event 实现跨线程信号传递。
"""

from __future__ import annotations

import threading
from typing import Any


class JobCancelledError(Exception):
    """任务被用户取消的异常"""
    pass


# 全局停止信号字典：run_id -> Event
_stop_events: dict[str, threading.Event] = {}
_stop_lock = threading.Lock()


def register_run(run_id: str) -> threading.Event:
    """注册一个运行中的任务，返回用于接收停止信号的 Event 对象"""
    ev = threading.Event()
    with _stop_lock:
        _stop_events[run_id] = ev
    return ev


def unregister_run(run_id: str) -> None:
    """任务结束后清理停止信号，防止内存泄漏"""
    with _stop_lock:
        _stop_events.pop(run_id, None)


def request_stop(run_id: str) -> bool:
    """请求停止指定 run_id 的任务。返回 True 表示成功发送停止信号。"""
    with _stop_lock:
        ev = _stop_events.get(run_id)
        if ev is not None:
            ev.set()
            return True
        return False


def is_stop_requested(run_id: str) -> bool:
    """检查指定 run_id 的任务是否被请求停止（供任务内部使用）"""
    with _stop_lock:
        ev = _stop_events.get(run_id)
        if ev is not None and ev.is_set():
            return True
        return False
