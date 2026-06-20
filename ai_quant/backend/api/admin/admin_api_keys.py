"""
API密钥管理路由模块

提供API密钥的CRUD操作和连通性测试功能。
支持多种密钥类型：DASHSCOPE、DEEPSEEK、TAVILY、TUSHARE
密钥存储时使用Fernet加密，响应格式统一为 {"ok": true, "data": ...}
"""

from __future__ import annotations

import uuid
from datetime import datetime

import requests
from fastapi import APIRouter
from pydantic import BaseModel

from ..admin_db import get_admin_db
from ...infra.crypto import encrypt_value, decrypt_value

router = APIRouter(prefix="/api/v1/admin/api-keys", tags=["admin-api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str
    provider: str
    key_type: str
    plain_key: str


class UpdateApiKeyRequest(BaseModel):
    name: str | None = None
    provider: str | None = None
    key_type: str | None = None
    plain_key: str | None = None
    status: str | None = None


def _key_prefix(cipher_text: str) -> str:
    try:
        plain = decrypt_value(cipher_text)
        return plain[:8]
    except Exception:
        return ""


def _test_dashscope(api_key: str) -> tuple[bool, str]:
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


def _test_deepseek(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.get(
            "https://api.deepseek.com/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "连接成功"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


def _test_tavily(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": "test", "max_results": 1},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "连接成功"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


def _test_tushare(api_key: str) -> tuple[bool, str]:
    try:
        resp = requests.post(
            "https://api.tushare.pro",
            json={
                "api_name": "stock_basic",
                "token": api_key,
                "params": {"ts_code": "000001.SZ"},
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 0:
            return True, "连接成功"
        return False, f"接口返回错误: {data.get('msg', '未知错误')}"
    except Exception as e:
        return False, str(e)


_TEST_FUNCTIONS = {
    "DASHSCOPE": _test_dashscope,
    "DEEPSEEK": _test_deepseek,
    "TAVILY": _test_tavily,
    "TUSHARE": _test_tushare,
}


@router.get("")
def list_api_keys():
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name, provider, key_type, cipher_key, status, created_at, updated_at "
                "FROM admin_api_keys ORDER BY updated_at DESC"
            )
            rows = cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["key_prefix"] = _key_prefix(d.pop("cipher_key"))
                result.append(d)
            return {"ok": True, "data": result}
        finally:
            conn.close()


@router.post("")
def create_api_key(req: CreateApiKeyRequest):
    cipher = encrypt_value(req.plain_key)
    now = datetime.now().isoformat()
    kid = uuid.uuid4().hex

    conn, lock = get_admin_db()
    with lock:
        try:
            conn.execute(
                "INSERT INTO admin_api_keys (id, name, provider, key_type, cipher_key, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                (kid, req.name, req.provider, req.key_type, cipher, now, now),
            )
            conn.commit()
            return {
                "ok": True,
                "data": {
                    "id": kid,
                    "name": req.name,
                    "provider": req.provider,
                    "key_type": req.key_type,
                    "key_prefix": req.plain_key[:8],
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                },
            }
        finally:
            conn.close()


@router.put("/{key_id}")
def update_api_key(key_id: str, req: UpdateApiKeyRequest):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_api_keys WHERE id = ?", (key_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "API密钥不存在"}

            fields = []
            values = []
            if req.name is not None:
                fields.append("name = ?")
                values.append(req.name)
            if req.provider is not None:
                fields.append("provider = ?")
                values.append(req.provider)
            if req.key_type is not None:
                fields.append("key_type = ?")
                values.append(req.key_type)
            if req.plain_key is not None:
                fields.append("cipher_key = ?")
                values.append(encrypt_value(req.plain_key))
            if req.status is not None:
                fields.append("status = ?")
                values.append(req.status)

            if not fields:
                return {"ok": False, "error": "没有需要更新的字段"}

            now = datetime.now().isoformat()
            fields.append("updated_at = ?")
            values.append(now)
            values.append(key_id)

            conn.execute(
                f"UPDATE admin_api_keys SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()

            cur.execute(
                "SELECT id, name, provider, key_type, cipher_key, status, created_at, updated_at "
                "FROM admin_api_keys WHERE id = ?",
                (key_id,),
            )
            row = dict(cur.fetchone())
            row["key_prefix"] = _key_prefix(row.pop("cipher_key"))
            return {"ok": True, "data": row}
        finally:
            conn.close()


@router.delete("/{key_id}")
def delete_api_key(key_id: str):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_api_keys WHERE id = ?", (key_id,))
            if not cur.fetchone():
                return {"ok": False, "error": "API密钥不存在"}

            conn.execute("DELETE FROM admin_api_keys WHERE id = ?", (key_id,))
            conn.commit()
            return {"ok": True, "data": {"id": key_id}}
        finally:
            conn.close()


@router.post("/{key_id}/test")
def test_api_key(key_id: str):
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT key_type, cipher_key FROM admin_api_keys WHERE id = ?",
                (key_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "API密钥不存在"}
            key_type = row["key_type"]
            cipher_key = row["cipher_key"]
        finally:
            conn.close()

    try:
        plain_key = decrypt_value(cipher_key)
    except Exception as e:
        return {"ok": False, "error": f"解密失败: {e}"}

    test_fn = _TEST_FUNCTIONS.get(key_type.upper())
    if not test_fn:
        return {
            "ok": False,
            "error": f"不支持的密钥类型: {key_type}，支持的类型: {', '.join(_TEST_FUNCTIONS.keys())}",
        }

    success, message = test_fn(plain_key)
    return {"ok": success, "data": {"success": success, "message": message}}
