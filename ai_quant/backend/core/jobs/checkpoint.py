"""
任务检查点管理工具

用于实现采集任务的断点续传功能：
1. 定期保存任务进度（检查点）
2. 任务中断后读取检查点恢复进度
3. 任务完成后清理检查点
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _checkpoint_dir() -> Path:
    """获取检查点存储目录"""
    # 优先使用环境变量指定的目录
    env_dir = os.getenv("AI_QUANT_CHECKPOINT_DIR", "")
    if env_dir:
        base = Path(env_dir)
    else:
        base = Path(os.path.dirname(__file__)) / ".." / ".." / ".ai_quant"
    cp_dir = base.resolve() / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    return cp_dir


def save_checkpoint(run_id: str, data: dict[str, Any]) -> None:
    """保存任务检查点

    原子写入：先写临时文件，再重命名，防止写入过程中进程崩溃导致文件损坏。

    Args:
        run_id: 任务运行ID
        data: 检查点数据，包含 processed_codes、failed_codes 等
    """
    if not run_id:
        return
    cp_dir = _checkpoint_dir()
    tmp = cp_dir / f".{run_id}.ckpt.tmp"
    out = cp_dir / f"{run_id}.ckpt"
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(out)
    except Exception as e:
        from core.jobs.domains.stock_daily import _log
        _log(f"[Checkpoint] 保存检查点失败: {type(e).__name__}: {e}")


def load_checkpoint(run_id: str) -> dict[str, Any] | None:
    """读取任务检查点

    Args:
        run_id: 任务运行ID

    Returns:
        检查点数据字典，不存在时返回 None
    """
    if not run_id:
        return None
    cp_file = _checkpoint_dir() / f"{run_id}.ckpt"
    if not cp_file.exists():
        return None
    try:
        return json.loads(cp_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_checkpoint(run_id: str) -> None:
    """删除任务检查点（任务完成后调用）

    Args:
        run_id: 任务运行ID
    """
    if not run_id:
        return
    cp_file = _checkpoint_dir() / f"{run_id}.ckpt"
    try:
        if cp_file.exists():
            cp_file.unlink()
    except Exception:
        pass


def get_checkpoint_position(run_id: str) -> tuple[int, list[str], list[str]]:
    """获取检查点中的任务进度位置

    Args:
        run_id: 任务运行ID

    Returns:
        (已处理数量, 已处理代码列表, 已失败代码列表)
    """
    cp = load_checkpoint(run_id)
    if cp is None:
        return 0, [], []
    processed = cp.get("processed_codes", [])
    failed = cp.get("failed_codes", [])
    total_done = len(processed) + len(failed)
    return total_done, processed, failed
