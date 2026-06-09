"""
工具与技能管理API路由模块

提供工具和技能的列表、启用/禁用、详情查看和配置更新功能。
工具来源于 backend/llm/tools/tools/ 注册的工具定义。
技能来源于 backend/llm/skills/ 下每个目录的 SKILL.md 元数据。
启用/禁用状态和配置存储在 admin_tools 表中。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from ..admin_db import get_admin_db

router = APIRouter(prefix="/api/v1/admin/tools", tags=["admin-tools"])

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class UpdateEnabledRequest(BaseModel):
    enabled: bool


class UpdateConfigRequest(BaseModel):
    config: dict


def _scan_skills() -> list[dict]:
    """扫描 llm/skills/ 目录，读取每个子目录的 SKILL.md 获取技能元数据"""
    skills_dir = _BACKEND_DIR / "llm" / "skills"
    if not skills_dir.exists():
        return []

    results = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue

        content = skill_md.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        name = entry.name
        description = ""
        keywords = ""
        in_front_matter = False
        for line in lines:
            stripped = line.strip()
            if stripped == "---":
                if not in_front_matter:
                    in_front_matter = True
                else:
                    break
            elif in_front_matter:
                if stripped.startswith("name:"):
                    parsed_name = stripped[len("name:"):].strip().strip('"').strip("'")
                    if parsed_name:
                        name = parsed_name
                elif stripped.startswith("description:"):
                    description = stripped[len("description:"):].strip().strip('"').strip("'")
                elif stripped.startswith("keywords:"):
                    keywords = stripped[len("keywords:"):].strip().strip('"').strip("'")

        if not description:
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("# ") and len(stripped) > 2:
                    continue
                if stripped and not stripped.startswith("---"):
                    description = stripped[:200]
                    break

        results.append({
            "name": name,
            "category": "skill",
            "description": description,
            "keywords": keywords,
            "path": str(skill_md.relative_to(_BACKEND_DIR)),
        })

    return results


def _scan_tools() -> list[dict]:
    """读取 llm/tools/tools/__init__.py 中注册的工具定义"""
    try:
        from ...llm.tools import list_tool_defs

        defs = list_tool_defs()
        results = []
        for t in defs:
            results.append({
                "name": t.get("name", ""),
                "category": "tool",
                "title": t.get("title", ""),
                "description": t.get("description", ""),
                "tags": t.get("tags", []),
                "input_schema": t.get("input_schema", {}),
            })
        return results
    except Exception:
        return []


def _get_db_map() -> dict[str, dict]:
    """从 admin_tools 表读取所有工具/技能的启用状态和配置"""
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT name, enabled, config_json FROM admin_tools")
            rows = cur.fetchall()
            result = {}
            for r in rows:
                try:
                    config = json.loads(r["config_json"])
                except Exception:
                    config = {}
                result[r["name"]] = {
                    "enabled": bool(r["enabled"]),
                    "config": config,
                }
            return result
        finally:
            conn.close()


def _ensure_db_entry(name: str):
    """确保数据库中有该工具/技能的记录"""
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM admin_tools WHERE name = ?", (name,))
            if not cur.fetchone():
                now = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO admin_tools (id, name, category, enabled, config_json, created_at, updated_at) "
                    "VALUES (?, ?, ?, 1, '{}', ?, ?)",
                    (uuid.uuid4().hex, name, "", now, now),
                )
                conn.commit()
        finally:
            conn.close()


@router.get("")
def list_tools_and_skills():
    tools = _scan_tools()
    skills = _scan_skills()
    db_map = _get_db_map()

    merged = []
    for item in tools + skills:
        name = item["name"]
        db_entry = db_map.get(name, {})
        item["enabled"] = db_entry.get("enabled", True)
        merged.append(item)

    return {"ok": True, "data": merged}


@router.put("/{name}/enabled")
def toggle_tool_enabled(name: str, req: UpdateEnabledRequest):
    _ensure_db_entry(name)

    conn, lock = get_admin_db()
    with lock:
        try:
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE admin_tools SET enabled = ?, updated_at = ? WHERE name = ?",
                (1 if req.enabled else 0, now, name),
            )
            conn.commit()
            return {"ok": True, "data": {"name": name, "enabled": req.enabled}}
        finally:
            conn.close()


@router.get("/{name}")
def get_tool_detail(name: str):
    tools = _scan_tools()
    skills = _scan_skills()

    item = None
    for t in tools:
        if t["name"] == name:
            item = {"type": "tool", **t}
            break
    if not item:
        for s in skills:
            if s["name"] == name:
                item = {"type": "skill", **s}
                break

    if not item:
        return {"ok": False, "error": f"工具/技能不存在: {name}"}

    db_map = _get_db_map()
    db_entry = db_map.get(name, {})
    item["enabled"] = db_entry.get("enabled", True)
    item["config"] = db_entry.get("config", {})

    return {"ok": True, "data": item}


@router.put("/{name}/config")
def update_tool_config(name: str, req: UpdateConfigRequest):
    _ensure_db_entry(name)

    conn, lock = get_admin_db()
    with lock:
        try:
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE admin_tools SET config_json = ?, updated_at = ? WHERE name = ?",
                (json.dumps(req.config, ensure_ascii=False), now, name),
            )
            conn.commit()
            return {"ok": True, "data": {"name": name, "config": req.config}}
        finally:
            conn.close()
