"""
系统配置API路由模块

提供系统配置的查询和批量更新功能。
配置数据存储在 admin_system_settings 表中，以 key-value 形式管理。
响应格式统一为 {"ok": true, "data": ...} 或 {"ok": false, "error": "..."}
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from ..admin_db import get_admin_db

router = APIRouter(prefix="/api/v1/admin/system", tags=["admin-system"])


class UpdateSystemSettingsRequest(BaseModel):
    settings: dict[str, str]


def _get_all_settings() -> dict[str, str]:
    """获取所有系统配置，以 key-value 字典形式返回"""
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT key, value FROM admin_system_settings ORDER BY key ASC"
            )
            return {row["key"]: row["value"] for row in cur.fetchall()}
        finally:
            conn.close()


@router.get("")
def get_system_settings():
    settings = _get_all_settings()
    return {"ok": True, "data": settings}


@router.put("")
def update_system_settings(req: UpdateSystemSettingsRequest):
    conn, lock = get_admin_db()
    with lock:
        try:
            now = datetime.now().isoformat()
            for key, value in req.settings.items():
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM admin_system_settings WHERE key = ?",
                    (key,),
                )
                if cur.fetchone()[0] > 0:
                    conn.execute(
                        "UPDATE admin_system_settings SET value = ?, updated_at = ? WHERE key = ?",
                        (value, now, key),
                    )
                else:
                    conn.execute(
                        "INSERT INTO admin_system_settings (id, key, value, description, updated_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex, key, value, "", now),
                    )
            conn.commit()
            return {"ok": True, "data": _get_all_settings()}
        finally:
            conn.close()
