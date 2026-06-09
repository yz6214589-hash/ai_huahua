"""
模型管理API路由模块

提供LLM模型配置的CRUD操作、连通性测试和状态切换功能。
数据存储在 admin_llm_models 表中，api_key_ref 关联 admin_api_keys 表。
响应格式统一为 {"ok": true, "data": ...} 或 {"ok": false, "error": "..."}
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import requests
from fastapi import APIRouter
from pydantic import BaseModel

from ..admin_db import get_admin_db
from ...infra.crypto import decrypt_value

router = APIRouter(prefix="/api/v1/admin/models", tags=["admin-models"])


class CreateModelRequest(BaseModel):
    name: str
    provider: str
    model_name: str
    api_key_ref: str | None = None
    base_url: str | None = None
    sort_order: int = 0


class UpdateModelRequest(BaseModel):
    name: str | None = None
    provider: str | None = None
    model_name: str | None = None
    api_key_ref: str | None = None
    base_url: str | None = None
    sort_order: int | None = None


class UpdateModelStatusRequest(BaseModel):
    status: str


def _get_decrypted_key(api_key_ref: str | None) -> str | None:
    if not api_key_ref:
        return None
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT cipher_key FROM admin_api_keys WHERE id = ? AND status = 'active'",
                (api_key_ref,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return decrypt_value(row["cipher_key"])
        except Exception:
            return None
        finally:
            conn.close()


def _test_tongyi(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            "https://dashscope.aliyuncs.com/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "连接成功"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


def _test_deepseek(api_key: str, base_url: str | None = None) -> tuple[bool, str]:
    url = (base_url or "https://api.deepseek.com").rstrip("/") + "/chat/completions"
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "连接成功"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


def _test_openai(api_key: str, base_url: str | None = None) -> tuple[bool, str]:
    url = (base_url or "https://api.openai.com").rstrip("/") + "/v1/models"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "连接成功"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


def _test_ollama(base_url: str | None = None) -> tuple[bool, str]:
    url = (base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return True, "连接成功"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


_TEST_FUNCTIONS = {
    "tongyi": _test_tongyi,
    "deepseek": _test_deepseek,
    "openai": _test_openai,
    "ollama": _test_ollama,
}


@router.get("")
def list_models():
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name, provider, model_name, api_key_ref, base_url, status, sort_order, created_at, updated_at "
                "FROM admin_llm_models ORDER BY sort_order ASC, updated_at DESC"
            )
            rows = cur.fetchall()
            return {"ok": True, "data": [dict(r) for r in rows]}
        finally:
            conn.close()


@router.post("")
def create_model(req: CreateModelRequest):
    now = datetime.now().isoformat()
    mid = uuid.uuid4().hex

    conn, lock = get_admin_db()
    with lock:
        try:
            conn.execute(
                "INSERT INTO admin_llm_models (id, name, provider, model_name, api_key_ref, base_url, status, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)",
                (mid, req.name, req.provider, req.model_name, req.api_key_ref, req.base_url, req.sort_order, now, now),
            )
            conn.commit()
            return {
                "ok": True,
                "data": {
                    "id": mid,
                    "name": req.name,
                    "provider": req.provider,
                    "model_name": req.model_name,
                    "api_key_ref": req.api_key_ref,
                    "base_url": req.base_url,
                    "status": "active",
                    "sort_order": req.sort_order,
                    "created_at": now,
                    "updated_at": now,
                },
            }
        finally:
            conn.close()


@router.put("/{model_id}")
def update_model(model_id: str, req: UpdateModelRequest):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_llm_models WHERE id = ?", (model_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "模型配置不存在"}

            fields = []
            values = []
            if req.name is not None:
                fields.append("name = ?")
                values.append(req.name)
            if req.provider is not None:
                fields.append("provider = ?")
                values.append(req.provider)
            if req.model_name is not None:
                fields.append("model_name = ?")
                values.append(req.model_name)
            if req.api_key_ref is not None:
                fields.append("api_key_ref = ?")
                values.append(req.api_key_ref)
            if req.base_url is not None:
                fields.append("base_url = ?")
                values.append(req.base_url)
            if req.sort_order is not None:
                fields.append("sort_order = ?")
                values.append(req.sort_order)

            if not fields:
                return {"ok": False, "error": "没有需要更新的字段"}

            now = datetime.now().isoformat()
            fields.append("updated_at = ?")
            values.append(now)
            values.append(model_id)

            conn.execute(
                f"UPDATE admin_llm_models SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()

            cur.execute(
                "SELECT id, name, provider, model_name, api_key_ref, base_url, status, sort_order, created_at, updated_at "
                "FROM admin_llm_models WHERE id = ?",
                (model_id,),
            )
            return {"ok": True, "data": dict(cur.fetchone())}
        finally:
            conn.close()


@router.delete("/{model_id}")
def delete_model(model_id: str):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_llm_models WHERE id = ?", (model_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "模型配置不存在"}

            conn.execute("DELETE FROM admin_llm_models WHERE id = ?", (model_id,))
            conn.commit()
            return {"ok": True, "data": {"id": model_id}}
        finally:
            conn.close()


@router.post("/{model_id}/test")
def test_model(model_id: str):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT provider, model_name, api_key_ref, base_url FROM admin_llm_models WHERE id = ?",
                (model_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "模型配置不存在"}
            provider = row["provider"]
            model_name = row["model_name"]
            api_key_ref = row["api_key_ref"]
            base_url = row["base_url"]
        finally:
            conn.close()

    key = _get_decrypted_key(api_key_ref)

    provider_lower = provider.strip().lower()

    if provider_lower == "ollama":
        success, message = _test_ollama(base_url)
        return {"ok": success, "data": {"success": success, "message": message}}

    if not key:
        return {"ok": False, "error": "无法获取API密钥，请检查密钥配置和状态"}

    if provider_lower == "tongyi":
        success, message = _test_tongyi(key)
    elif provider_lower == "deepseek":
        success, message = _test_deepseek(key, base_url)
    elif provider_lower == "openai":
        success, message = _test_openai(key, base_url)
    else:
        return {"ok": False, "error": f"不支持的 provider: {provider}，支持的类型: tongyi, deepseek, openai, ollama"}

    return {"ok": success, "data": {"success": success, "message": message}}


@router.put("/{model_id}/status")
def toggle_model_status(model_id: str, req: UpdateModelStatusRequest):
    valid_statuses = {"active", "disabled"}
    if req.status not in valid_statuses:
        return {"ok": False, "error": f"无效的状态值，必须为: {', '.join(sorted(valid_statuses))}"}

    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_llm_models WHERE id = ?", (model_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "模型配置不存在"}

            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE admin_llm_models SET status = ?, updated_at = ? WHERE id = ?",
                (req.status, now, model_id),
            )
            conn.commit()

            cur.execute(
                "SELECT id, name, provider, model_name, api_key_ref, base_url, status, sort_order, created_at, updated_at "
                "FROM admin_llm_models WHERE id = ?",
                (model_id,),
            )
            return {"ok": True, "data": dict(cur.fetchone())}
        finally:
            conn.close()
