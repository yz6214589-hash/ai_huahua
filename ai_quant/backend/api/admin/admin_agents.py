"""
智能体配置API路由模块

提供智能体配置的CRUD操作和默认智能体列表功能。
数据存储在 admin_agents 表中，model_id 关联 admin_llm_models 表，
prompt_id 关联 admin_prompts 表，响应中自动解析关联名称。
响应格式统一为 {"ok": true, "data": ...} 或 {"ok": false, "error": "..."}
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from ..admin_db import get_admin_db
from ...llm.prompt_manager import PromptManager

router = APIRouter(prefix="/api/v1/admin/agents", tags=["admin-agents"])


class CreateAgentRequest(BaseModel):
    role: str
    name: str
    description: str | None = None
    model_id: str | None = None
    skills: list[str] = []
    tools: list[str] = []
    prompt_id: str | None = None


class UpdateAgentRequest(BaseModel):
    role: str | None = None
    name: str | None = None
    description: str | None = None
    model_id: str | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    prompt_id: str | None = None


def _resolve_model_name(model_id: str | None) -> str | None:
    """关联查询模型名称"""
    if not model_id:
        return None
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM admin_llm_models WHERE id = ?", (model_id,))
            row = cur.fetchone()
            if row:
                return row["name"]
            return None
        finally:
            conn.close()


def _resolve_prompt_name(prompt_id: str | None) -> str | None:
    """关联查询提示词名称"""
    if not prompt_id:
        return None
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT category, name FROM admin_prompts WHERE id = ?", (prompt_id,))
            row = cur.fetchone()
            if row:
                return f"{row['category']}/{row['name']}"
            return None
        finally:
            conn.close()


def _agent_row_to_dict(row) -> dict:
    """将数据库行转换为响应字典，包含关联名称"""
    d = dict(row)
    for field in ("skills", "tools"):
        try:
            if isinstance(d.get(field), str):
                d[field] = json.loads(d[field])
            elif d.get(field) is None:
                d[field] = []
        except Exception:
            d[field] = []
    d["model_name"] = _resolve_model_name(d.get("model_id"))
    d["prompt_name"] = _resolve_prompt_name(d.get("prompt_id"))
    return d


@router.get("")
def list_agents():
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, role, name, description, model_id, skills, tools, prompt_id, created_at, updated_at "
                "FROM admin_agents ORDER BY role ASC"
            )
            rows = cur.fetchall()
            return {"ok": True, "data": [_agent_row_to_dict(r) for r in rows]}
        finally:
            conn.close()


@router.post("")
def create_agent(req: CreateAgentRequest):
    now = datetime.now().isoformat()
    aid = uuid.uuid4().hex
    conn, lock = get_admin_db()
    with lock:
        try:
            conn.execute(
                "INSERT INTO admin_agents (id, role, name, description, model_id, skills, tools, prompt_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    aid,
                    req.role,
                    req.name,
                    req.description,
                    req.model_id,
                    json.dumps(req.skills, ensure_ascii=False),
                    json.dumps(req.tools, ensure_ascii=False),
                    req.prompt_id,
                    now,
                    now,
                ),
            )
            conn.commit()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, role, name, description, model_id, skills, tools, prompt_id, created_at, updated_at "
                "FROM admin_agents WHERE id = ?",
                (aid,),
            )
            return {"ok": True, "data": _agent_row_to_dict(cur.fetchone())}
        finally:
            conn.close()


@router.put("/{agent_id}")
def update_agent(agent_id: str, req: UpdateAgentRequest):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_agents WHERE id = ?", (agent_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "智能体配置不存在"}
            fields = []
            values = []
            if req.role is not None:
                fields.append("role = ?")
                values.append(req.role)
            if req.name is not None:
                fields.append("name = ?")
                values.append(req.name)
            if req.description is not None:
                fields.append("description = ?")
                values.append(req.description)
            if req.model_id is not None:
                fields.append("model_id = ?")
                values.append(req.model_id)
            if req.skills is not None:
                fields.append("skills = ?")
                values.append(json.dumps(req.skills, ensure_ascii=False))
            if req.tools is not None:
                fields.append("tools = ?")
                values.append(json.dumps(req.tools, ensure_ascii=False))
            if req.prompt_id is not None:
                fields.append("prompt_id = ?")
                values.append(req.prompt_id)
            if not fields:
                return {"ok": False, "error": "没有需要更新的字段"}
            now = datetime.now().isoformat()
            fields.append("updated_at = ?")
            values.append(now)
            values.append(agent_id)
            conn.execute(
                f"UPDATE admin_agents SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
            cur.execute(
                "SELECT id, role, name, description, model_id, skills, tools, prompt_id, created_at, updated_at "
                "FROM admin_agents WHERE id = ?",
                (agent_id,),
            )
            return {"ok": True, "data": _agent_row_to_dict(cur.fetchone())}
        finally:
            conn.close()


@router.delete("/{agent_id}")
def delete_agent(agent_id: str):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_agents WHERE id = ?", (agent_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "智能体配置不存在"}
            conn.execute("DELETE FROM admin_agents WHERE id = ?", (agent_id,))
            conn.commit()
            return {"ok": True, "data": {"id": agent_id}}
        finally:
            conn.close()


_DEFAULT_AGENTS = [
    {"role": "charles", "name": "Charles", "description": "数据分析师，负责数据查询、股票筛选、技术分析", "model_id": None, "skills": ["data_analysis"], "tools": [], "prompt_id": None},
    {"role": "zoe", "name": "Zoe", "description": "行业研究员，负责基本面分析、财务分析、行业研究", "model_id": None, "skills": ["financial_analysis"], "tools": [], "prompt_id": None},
    {"role": "kris", "name": "Kris", "description": "风控专家，负责风险评估、仓位管理、止损策略", "model_id": None, "skills": ["risk_management"], "tools": [], "prompt_id": None},
    {"role": "ethan", "name": "Ethan", "description": "交易员，负责策略执行、订单管理、交易复盘", "model_id": None, "skills": ["trading"], "tools": [], "prompt_id": None},
    {"role": "ceo", "name": "CEO", "description": "投资决策官，负责整体策略制定、团队协调、投资决策", "model_id": None, "skills": ["decision_making"], "tools": [], "prompt_id": None},
]


@router.get("/defaults")
def get_default_agents():
    return {"ok": True, "data": _DEFAULT_AGENTS}


class AgentConfigManager:
    """智能体配置管理器，提供静态方法查询各角色的智能体配置"""

    @staticmethod
    def get_agent(role: str) -> dict:
        """获取指定角色的智能体配置"""
        conn, lock = get_admin_db()
        with lock:
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, role, name, description, model_id, skills, tools, prompt_id "
                    "FROM admin_agents WHERE role = ?",
                    (role,),
                )
                row = cur.fetchone()
                if not row:
                    return {}
                result = dict(row)
                for field in ("skills", "tools"):
                    try:
                        if isinstance(result.get(field), str):
                            result[field] = json.loads(result[field])
                        elif result.get(field) is None:
                            result[field] = []
                    except Exception:
                        result[field] = []
                return result
            finally:
                conn.close()

    @staticmethod
    def get_agent_model(role: str) -> str:
        """获取指定角色的模型ID"""
        config = AgentConfigManager.get_agent(role)
        return config.get("model_id") or ""

    @staticmethod
    def get_agent_tools(role: str) -> list[str]:
        """获取指定角色启用的工具列表"""
        config = AgentConfigManager.get_agent(role)
        return config.get("tools") or []

    @staticmethod
    def get_agent_skills(role: str) -> list[str]:
        """获取指定角色关联的技能列表"""
        config = AgentConfigManager.get_agent(role)
        return config.get("skills") or []

    @staticmethod
    def get_agent_prompt(role: str) -> str:
        """获取指定角色的提示词内容"""
        config = AgentConfigManager.get_agent(role)
        prompt_id = config.get("prompt_id")
        if prompt_id:
            conn, lock = get_admin_db()
            with lock:
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT content FROM admin_prompts WHERE id = ?",
                        (prompt_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        return row["content"]
                finally:
                    conn.close()
        return ""

    @staticmethod
    def get_agent_model_id(role: str) -> str | None:
        """获取指定角色的模型ID（原始值）"""
        config = AgentConfigManager.get_agent(role)
        return config.get("model_id")
