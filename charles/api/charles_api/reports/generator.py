from __future__ import annotations

import json

from ..db import MySQLConfig, connect
from .agents import build_report_agents
from .models import ReportModel
from .store import get_task, mark_failed, mark_running, mark_success


def run_report_task(mysql_cfg: MySQLConfig, task_id: str, root_dir: str) -> None:
    conn = connect(mysql_cfg)
    try:
        task = get_task(conn, task_id=task_id)
        mark_running(conn, task_id=task_id)
        conn.commit()
    finally:
        conn.close()

    try:
        model = task.model
        planner, researcher, writer, reviewer = build_report_agents(root_dir=root_dir, model=model)

        topic = "、".join(
            [
                f"{(task.stock_names[i] if i < len(task.stock_names) else '').strip()}{code}".strip()
                for i, code in enumerate(task.stock_codes)
            ]
        )
        user_prompt = f"为以下股票生成一份综合研报：{topic}。要求：行业格局、公司基本面、财务趋势、估值与预期差、催化剂、风险。"

        plan_res = planner.invoke({"messages": [{"role": "user", "content": user_prompt}]})
        plan_msg = (plan_res.get("messages") or [])[-1]
        plan_text = str(getattr(plan_msg, "content", "") or "")

        try:
            plan_obj = json.loads(plan_text)
        except Exception:
            plan_obj = {"outline": plan_text, "web_queries": [], "rag_queries": []}

        research_prompt = json.dumps(
            {
                "stock_codes": task.stock_codes,
                "stock_names": task.stock_names,
                "plan": plan_obj,
            },
            ensure_ascii=False,
            indent=2,
        )
        research_res = researcher.invoke({"messages": [{"role": "user", "content": research_prompt}]})
        research_msg = (research_res.get("messages") or [])[-1]
        research_text = str(getattr(research_msg, "content", "") or "")

        draft_res = writer.invoke({"messages": [{"role": "user", "content": research_text}]})
        draft_msg = (draft_res.get("messages") or [])[-1]
        draft_md = str(getattr(draft_msg, "content", "") or "")

        final_res = reviewer.invoke({"messages": [{"role": "user", "content": draft_md}]})
        final_msg = (final_res.get("messages") or [])[-1]
        final_md = str(getattr(final_msg, "content", "") or "")

        conn2 = connect(mysql_cfg)
        try:
            mark_success(conn2, task_id=task_id, report_markdown=final_md or draft_md)
            conn2.commit()
        finally:
            conn2.close()
    except Exception as e:
        conn3 = connect(mysql_cfg)
        try:
            mark_failed(conn3, task_id=task_id, error_message=f"{type(e).__name__}: {e}")
            conn3.commit()
        finally:
            conn3.close()

