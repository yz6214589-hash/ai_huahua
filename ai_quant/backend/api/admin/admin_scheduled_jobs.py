"""
AI定时任务API路由模块

提供AI定时任务的CRUD操作、立即执行和日志查询功能。
数据存储在 admin_ai_scheduled_tasks 和 admin_ai_task_logs 表中。
响应格式统一为 {"ok": true, "data": ...} 或 {"ok": false, "error": "..."}
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from ..admin_db import get_admin_db
from ...llm.deepagent_engine import run_deepagent

router = APIRouter(prefix="/api/v1/admin/scheduled-jobs", tags=["admin-scheduled-jobs"])

VALID_TASK_TYPES = {
    "sentiment_monitor",
    "first_board_scan",
    "feishu_sentiment",
    "feishu_first_board",
}


class CreateScheduledTaskRequest(BaseModel):
    name: str
    task_type: str
    cron_expr: str
    model_id: str | None = None
    prompt_id: str | None = None
    config: dict = {}


class UpdateScheduledTaskRequest(BaseModel):
    name: str | None = None
    task_type: str | None = None
    cron_expr: str | None = None
    model_id: str | None = None
    prompt_id: str | None = None
    enabled: bool | None = None
    config: dict | None = None


def _task_row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["config"] = json.loads(d["config_json"]) if isinstance(d["config_json"], str) else {}
    except Exception:
        d["config"] = {}
    d.pop("config_json", None)
    d["enabled"] = bool(d["enabled"])
    return d


@router.get("")
def list_scheduled_tasks():
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name, task_type, cron_expr, model_id, prompt_id, enabled, config_json, created_at, updated_at "
                "FROM admin_ai_scheduled_tasks ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
            return {"ok": True, "data": [_task_row_to_dict(r) for r in rows]}
        finally:
            conn.close()


@router.post("")
def create_scheduled_task(req: CreateScheduledTaskRequest):
    if req.task_type not in VALID_TASK_TYPES:
        return {
            "ok": False,
            "error": f"无效的任务类型，必须为: {', '.join(sorted(VALID_TASK_TYPES))}",
        }
    now = datetime.now().isoformat()
    tid = uuid.uuid4().hex
    conn, lock = get_admin_db()
    with lock:
        try:
            conn.execute(
                "INSERT INTO admin_ai_scheduled_tasks (id, name, task_type, cron_expr, model_id, prompt_id, enabled, config_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (
                    tid,
                    req.name,
                    req.task_type,
                    req.cron_expr,
                    req.model_id,
                    req.prompt_id,
                    json.dumps(req.config, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.commit()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name, task_type, cron_expr, model_id, prompt_id, enabled, config_json, created_at, updated_at "
                "FROM admin_ai_scheduled_tasks WHERE id = ?",
                (tid,),
            )
            return {"ok": True, "data": _task_row_to_dict(cur.fetchone())}
        finally:
            conn.close()


@router.put("/{task_id}")
def update_scheduled_task(task_id: str, req: UpdateScheduledTaskRequest):
    if req.task_type is not None and req.task_type not in VALID_TASK_TYPES:
        return {
            "ok": False,
            "error": f"无效的任务类型，必须为: {', '.join(sorted(VALID_TASK_TYPES))}",
        }
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_ai_scheduled_tasks WHERE id = ?", (task_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "定时任务不存在"}
            fields = []
            values = []
            if req.name is not None:
                fields.append("name = ?")
                values.append(req.name)
            if req.task_type is not None:
                fields.append("task_type = ?")
                values.append(req.task_type)
            if req.cron_expr is not None:
                fields.append("cron_expr = ?")
                values.append(req.cron_expr)
            if req.model_id is not None:
                fields.append("model_id = ?")
                values.append(req.model_id)
            if req.prompt_id is not None:
                fields.append("prompt_id = ?")
                values.append(req.prompt_id)
            if req.enabled is not None:
                fields.append("enabled = ?")
                values.append(1 if req.enabled else 0)
            if req.config is not None:
                fields.append("config_json = ?")
                values.append(json.dumps(req.config, ensure_ascii=False))
            if not fields:
                return {"ok": False, "error": "没有需要更新的字段"}
            now = datetime.now().isoformat()
            fields.append("updated_at = ?")
            values.append(now)
            values.append(task_id)
            conn.execute(
                f"UPDATE admin_ai_scheduled_tasks SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
            cur.execute(
                "SELECT id, name, task_type, cron_expr, model_id, prompt_id, enabled, config_json, created_at, updated_at "
                "FROM admin_ai_scheduled_tasks WHERE id = ?",
                (task_id,),
            )
            return {"ok": True, "data": _task_row_to_dict(cur.fetchone())}
        finally:
            conn.close()


@router.delete("/{task_id}")
def delete_scheduled_task(task_id: str):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_ai_scheduled_tasks WHERE id = ?", (task_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "定时任务不存在"}
            conn.execute("DELETE FROM admin_ai_scheduled_tasks WHERE id = ?", (task_id,))
            conn.commit()
            return {"ok": True, "data": {"id": task_id}}
        finally:
            conn.close()


@router.post("/{task_id}/run")
def run_task_once(task_id: str):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name, task_type, model_id, prompt_id, config_json "
                "FROM admin_ai_scheduled_tasks WHERE id = ?",
                (task_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "定时任务不存在"}
            task = dict(row)
        finally:
            conn.close()

    try:
        import threading
        t = threading.Thread(
            target=AITaskRunner.run_task,
            args=(task_id,),
            daemon=True,
        )
        t.start()
        return {"ok": True, "data": {"message": "任务已启动执行", "task_id": task_id, "task_name": task["name"]}}
    except Exception as e:
        return {"ok": False, "error": f"启动任务失败: {e}"}


@router.get("/{task_id}/logs")
def get_task_logs(task_id: str, limit: int = 50):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_ai_scheduled_tasks WHERE id = ?", (task_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "定时任务不存在"}
        finally:
            conn.close()
    logs = AITaskRunner.get_task_logs(task_id, limit)
    return {"ok": True, "data": logs}


_TASK_PROMPTS = {
    "sentiment_monitor": "执行舆情监控扫描任务。请搜索当前市场主要舆情热点，重点关注影响A股市场的重要新闻、政策变化和行业动态，汇总成简要报告。",
    "first_board_scan": "执行首板扫描任务。请分析当前A股市场涨停板情况，识别首次涨停的股票，分析其涨停原因和后续走势预期。",
    "feishu_sentiment": "生成飞书推送-舆情日报内容。请整理今日舆情监控结果，形成适合飞书推送的简洁日报格式。",
    "feishu_first_board": "生成飞书推送-首板机会内容。请整理今日首板扫描结果，形成适合飞书推送的简洁机会报告格式。",
}


class AITaskRunner:
    """AI任务运行器，提供静态方法执行AI任务和查询日志"""

    @staticmethod
    def run_task(task_id: str) -> dict:
        """执行AI任务，调用DeepAgent执行"""
        conn, lock = get_admin_db()
        with lock:
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, name, task_type, model_id, prompt_id, config_json "
                    "FROM admin_ai_scheduled_tasks WHERE id = ?",
                    (task_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {"ok": False, "error": "定时任务不存在"}
                task = dict(row)
            finally:
                conn.close()

        log_id = uuid.uuid4().hex
        started_at = datetime.now().isoformat()

        try:
            config = json.loads(task["config_json"]) if isinstance(task["config_json"], str) else {}
        except Exception:
            config = {}

        conn, lock = get_admin_db()
        with lock:
            try:
                conn.execute(
                    "INSERT INTO admin_ai_task_logs (id, task_id, status, started_at, result, error_message) "
                    "VALUES (?, ?, 'running', ?, '', '')",
                    (log_id, task_id, started_at),
                )
                conn.commit()
            finally:
                conn.close()

        try:
            prompt_text = _TASK_PROMPTS.get(task["task_type"], "")
            user_config = config.get("prompt_extra", "")
            if user_config:
                prompt_text = prompt_text + "\n\n额外要求:\n" + str(user_config)

            result = run_deepagent(
                prompt_text,
                thread_id=f"task_{task_id}",
                max_steps=8,
            )

            finished_at = datetime.now().isoformat()
            conn, lock = get_admin_db()
            with lock:
                try:
                    conn.execute(
                        "UPDATE admin_ai_task_logs SET status = 'success', finished_at = ?, result = ?, error_message = '' WHERE id = ?",
                        (finished_at, result.text, log_id),
                    )
                    conn.commit()
                finally:
                    conn.close()

            return {"ok": True, "data": {"log_id": log_id, "result": result.text, "steps": result.steps}}

        except Exception as e:
            finished_at = datetime.now().isoformat()
            error_msg = f"{type(e).__name__}: {e}"
            conn, lock = get_admin_db()
            with lock:
                try:
                    conn.execute(
                        "UPDATE admin_ai_task_logs SET status = 'failed', finished_at = ?, result = '', error_message = ? WHERE id = ?",
                        (finished_at, error_msg, log_id),
                    )
                    conn.commit()
                finally:
                    conn.close()
            return {"ok": False, "error": error_msg}

    @staticmethod
    def get_task_logs(task_id: str, limit: int = 50) -> list[dict]:
        """获取任务执行日志"""
        conn, lock = get_admin_db()
        with lock:
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, task_id, status, started_at, finished_at, result, error_message "
                    "FROM admin_ai_task_logs WHERE task_id = ? ORDER BY started_at DESC LIMIT ?",
                    (task_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()
