"""
会话管理增强 API 模块

提供管理后台的会话列表和统计功能：
- 会话列表（带消息数统计和来源推断）
- 会话统计（按来源分类）
- 会话详情（含消息列表）
- 支持标题模糊搜索和来源筛选

复用了 conversations.db 数据库，与 conversation_api.py 共享数据存储
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/admin/conversations", tags=["admin-conversations"])

_DB_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".data"
_DB_PATH = _DB_DIR / "conversations.db"

_lock = threading.Lock()


def _get_conv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _infer_source(conv_id: str, title: str) -> str:
    if conv_id.startswith("feishu_"):
        return "feishu_private"
    if title.startswith("[群聊]"):
        return "feishu_group"
    return "system"


@router.get("")
def list_conversations(
    search: str | None = Query(None, description="模糊搜索标题"),
    source: str | None = Query(None, description="来源筛选: feishu_private|feishu_group|system"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    conn = _get_conv_db()
    with _lock:
        try:
            where_clauses = []
            params = []

            if search:
                where_clauses.append("c.title LIKE ?")
                params.append(f"%{search}%")

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            # 先获取总数
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM conversations c {where_sql}",
                params,
            )
            total = cur.fetchone()[0]

            # 再获取分页数据，包含 last_message_time
            offset = (page - 1) * page_size
            cur.execute(
                f"""
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count,
                       (SELECT MAX(m2.created_at) FROM messages m2 WHERE m2.conversation_id = c.id) AS last_message_time
                FROM conversations c
                {where_sql}
                ORDER BY c.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            )
            rows = cur.fetchall()

            data = []
            for r in rows:
                d = dict(r)
                d["source"] = _infer_source(d["id"], d["title"])
                data.append(d)

            # 如果指定了 source 筛选，在内存中过滤
            if source:
                data = [d for d in data if d["source"] == source]
                total = len(data)

            return {
                "ok": True,
                "data": {
                    "items": data,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                },
            }
        finally:
            conn.close()


@router.get("/stats")
def conversation_stats():
    conn = _get_conv_db()
    with _lock:
        try:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM conversations")
            total = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM messages")
            total_messages = cur.fetchone()[0]

            # 由于 conversations.db 没有 source 字段，全部归为 system
            cur.execute("SELECT COUNT(*) FROM conversations WHERE id NOT LIKE 'feishu_%'")
            system_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM conversations WHERE id LIKE 'feishu_%'")
            feishu_total = cur.fetchone()[0]

            return {
                "ok": True,
                "data": {
                    "total_conversations": total,
                    "total_messages": total_messages,
                    "feishu_private": feishu_total,
                    "feishu_group": 0,
                    "system": system_count,
                },
            }
        finally:
            conn.close()


@router.get("/{conv_id}")
def get_conversation_detail(
    conv_id: str,
    page: int = Query(1, ge=1, description="消息页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页消息数"),
):
    """获取会话详情，包含分页消息列表"""
    conn = _get_conv_db()
    with _lock:
        try:
            cur = conn.cursor()

            # 获取会话信息
            cur.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                (conv_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "会话不存在"}

            conv = dict(row)
            conv["source"] = _infer_source(conv["id"], conv["title"])

            # 获取消息总数
            cur.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                (conv_id,),
            )
            total_messages = cur.fetchone()[0]

            # 获取分页消息列表
            offset = (page - 1) * page_size
            cur.execute(
                "SELECT id, role, content, metadata, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
                (conv_id, page_size, offset),
            )
            messages = []
            for m in cur.fetchall():
                m_dict = dict(m)
                try:
                    m_dict["metadata"] = json.loads(m_dict.get("metadata") or "{}")
                except Exception:
                    m_dict["metadata"] = {}
                messages.append(m_dict)

            conv["messages"] = messages
            conv["messages_total"] = total_messages
            conv["messages_page"] = page
            conv["messages_page_size"] = page_size
            return {"ok": True, "data": conv}
        finally:
            conn.close()


@router.put("/{conv_id}/title")
def update_conversation_title(conv_id: str, payload: dict):
    """更新会话标题"""
    new_title = (payload.get("title") or "").strip()
    if not new_title:
        return {"ok": False, "error": "标题不能为空"}
    if len(new_title) > 200:
        return {"ok": False, "error": "标题不能超过200个字符"}

    from datetime import datetime
    now = datetime.now().isoformat()

    conn = _get_conv_db()
    with _lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM conversations WHERE id = ?", (conv_id,)
            )
            if not cur.fetchone():
                return {"ok": False, "error": "会话不存在"}

            cur.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (new_title, now, conv_id),
            )
            conn.commit()
            return {"ok": True, "data": {"id": conv_id, "title": new_title}}
        finally:
            conn.close()
