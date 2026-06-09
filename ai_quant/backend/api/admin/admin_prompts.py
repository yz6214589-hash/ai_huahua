"""
提示词管理API路由模块

提供提示词模板的CRUD操作、版本管理和预览功能。
数据存储在 admin_prompts 表中，版本历史存储在 admin_prompt_versions 表中。
更新模板时自动创建新版本，旧版本存入版本历史表。
支持变量替换预览功能。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from ..admin_db import get_admin_db

router = APIRouter(prefix="/api/v1/admin/prompts", tags=["admin-prompts"])

VALID_CATEGORIES = {"system", "rag", "zoe", "other"}


class CreatePromptRequest(BaseModel):
    category: str
    name: str
    content: str
    variables: list[str] = []


class UpdatePromptRequest(BaseModel):
    content: str
    variables: list[str] | None = None


class PreviewPromptRequest(BaseModel):
    variables: dict = {}


@router.get("")
def list_prompts():
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, category, name, content, version, variables, created_at, updated_at "
                "FROM admin_prompts ORDER BY category ASC, name ASC"
            )
            rows = cur.fetchall()
            data = []
            for r in rows:
                d = dict(r)
                try:
                    d["variables"] = json.loads(d["variables"]) if isinstance(d["variables"], str) else d["variables"]
                except Exception:
                    d["variables"] = []
                data.append(d)
            return {"ok": True, "data": data}
        finally:
            conn.close()


@router.post("")
def create_prompt(req: CreatePromptRequest):
    if req.category not in VALID_CATEGORIES:
        return {"ok": False, "error": f"无效的分类，必须为: {', '.join(sorted(VALID_CATEGORIES))}"}

    now = datetime.now().isoformat()
    pid = uuid.uuid4().hex

    conn, lock = get_admin_db()
    with lock:
        try:
            conn.execute(
                "INSERT INTO admin_prompts (id, category, name, content, version, variables, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
                (pid, req.category, req.name, req.content, json.dumps(req.variables, ensure_ascii=False), now, now),
            )
            conn.commit()

            conn.execute(
                "INSERT INTO admin_prompt_versions (id, prompt_id, content, version, created_at) "
                "VALUES (?, ?, ?, 1, ?)",
                (uuid.uuid4().hex, pid, req.content, now),
            )
            conn.commit()

            return {
                "ok": True,
                "data": {
                    "id": pid,
                    "category": req.category,
                    "name": req.name,
                    "content": req.content,
                    "version": 1,
                    "variables": req.variables,
                    "created_at": now,
                    "updated_at": now,
                },
            }
        finally:
            conn.close()


@router.put("/{prompt_id}")
def update_prompt(prompt_id: str, req: UpdatePromptRequest):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, category, name, content, version, variables FROM admin_prompts WHERE id = ?",
                (prompt_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "提示词模板不存在"}

            old_content = row["content"]
            old_version = row["version"]
            new_version = old_version + 1
            now = datetime.now().isoformat()

            variables_json = row["variables"]
            if req.variables is not None:
                variables_json = json.dumps(req.variables, ensure_ascii=False)

            conn.execute(
                "UPDATE admin_prompts SET content = ?, version = ?, variables = ?, updated_at = ? WHERE id = ?",
                (req.content, new_version, variables_json, now, prompt_id),
            )

            conn.execute(
                "INSERT INTO admin_prompt_versions (id, prompt_id, content, version, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, prompt_id, req.content, new_version, now),
            )

            conn.commit()

            cur.execute(
                "SELECT id, category, name, content, version, variables, created_at, updated_at "
                "FROM admin_prompts WHERE id = ?",
                (prompt_id,),
            )
            result = dict(cur.fetchone())
            try:
                result["variables"] = json.loads(result["variables"]) if isinstance(result["variables"], str) else result["variables"]
            except Exception:
                result["variables"] = []

            return {"ok": True, "data": result}
        finally:
            conn.close()


@router.get("/{prompt_id}")
def get_prompt(prompt_id: str):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, category, name, content, version, variables, created_at, updated_at "
                "FROM admin_prompts WHERE id = ?",
                (prompt_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "提示词模板不存在"}
            result = dict(row)
            try:
                result["variables"] = json.loads(result["variables"]) if isinstance(result["variables"], str) else result["variables"]
            except Exception:
                result["variables"] = []
            return {"ok": True, "data": result}
        finally:
            conn.close()


@router.get("/{prompt_id}/versions")
def get_prompt_versions(prompt_id: str):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_prompts WHERE id = ?", (prompt_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "提示词模板不存在"}

            cur.execute(
                "SELECT id, prompt_id, content, version, created_at "
                "FROM admin_prompt_versions WHERE prompt_id = ? ORDER BY version DESC",
                (prompt_id,),
            )
            rows = cur.fetchall()
            return {"ok": True, "data": [dict(r) for r in rows]}
        finally:
            conn.close()


@router.post("/{prompt_id}/rollback/{version}")
def rollback_prompt(prompt_id: str, version: int):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, version FROM admin_prompts WHERE id = ?", (prompt_id,))
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "提示词模板不存在"}

            cur.execute(
                "SELECT content, version FROM admin_prompt_versions "
                "WHERE prompt_id = ? AND version = ?",
                (prompt_id, version),
            )
            version_row = cur.fetchone()
            if not version_row:
                return {"ok": False, "error": f"版本 {version} 不存在"}

            now = datetime.now().isoformat()
            new_version = row["version"] + 1

            conn.execute(
                "UPDATE admin_prompts SET content = ?, version = ?, updated_at = ? WHERE id = ?",
                (version_row["content"], new_version, now, prompt_id),
            )

            conn.execute(
                "INSERT INTO admin_prompt_versions (id, prompt_id, content, version, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, prompt_id, version_row["content"], new_version, now),
            )

            conn.commit()

            cur.execute(
                "SELECT id, category, name, content, version, variables, created_at, updated_at "
                "FROM admin_prompts WHERE id = ?",
                (prompt_id,),
            )
            result = dict(cur.fetchone())
            try:
                result["variables"] = json.loads(result["variables"]) if isinstance(result["variables"], str) else result["variables"]
            except Exception:
                result["variables"] = []

            return {"ok": True, "data": result}
        finally:
            conn.close()


@router.post("/{prompt_id}/preview")
def preview_prompt(prompt_id: str, req: PreviewPromptRequest):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT content, variables FROM admin_prompts WHERE id = ?",
                (prompt_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "提示词模板不存在"}

            content = row["content"]
            variables_raw = row["variables"]
            try:
                declared_vars = json.loads(variables_raw) if isinstance(variables_raw, str) else (variables_raw or [])
            except Exception:
                declared_vars = []

            rendered = content
            for var_name, var_value in req.variables.items():
                placeholder = "{" + var_name + "}"
                rendered = rendered.replace(placeholder, str(var_value))

            return {
                "ok": True,
                "data": {
                    "rendered": rendered,
                    "declared_variables": declared_vars,
                    "provided_variables": list(req.variables.keys()),
                },
            }
        finally:
            conn.close()
