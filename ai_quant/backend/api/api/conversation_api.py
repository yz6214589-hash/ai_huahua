"""
会话管理 API

提供对话会话的 CRUD 操作：
- GET  /api/conversations          -- 列出所有会话（按更新时间倒序）
- POST /api/conversations          -- 创建新会话
- GET  /api/conversations/{id}      -- 获取会话详情（含消息列表）
- PUT  /api/conversations/{id}      -- 更新会话（标题）
- DELETE /api/conversations/{id}    -- 删除会话
- POST /api/conversations/{id}/messages  -- 添加消息到会话
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

_DB_DIR = Path(__file__).resolve().parent.parent.parent / ".data"
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DB_DIR / "conversations.db"

_lock = threading.Lock()


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '新对话',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
        """)
        conn.commit()
    finally:
        conn.close()


_init_db()


class CreateConversationRequest(BaseModel):
    title: str | None = None


class UpdateConversationRequest(BaseModel):
    title: str


class AddMessageRequest(BaseModel):
    role: str
    content: str
    metadata: dict | None = None


@router.get("")
def list_conversations() -> list[dict]:
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("")
def create_conversation(req: CreateConversationRequest | None = None) -> dict:
    cid = uuid.uuid4().hex
    now = datetime.now().isoformat()
    title = req.title if req and req.title else "新对话"

    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (cid, title, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    return {"id": cid, "title": title, "created_at": now, "updated_at": now}


@router.get("/{conv_id}")
def get_conversation(conv_id: str) -> dict:
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conv_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在")

        cur.execute(
            "SELECT id, role, content, metadata, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,),
        )
        messages = []
        for m in cur.fetchall():
            m_dict = dict(m)
            try:
                m_dict["metadata"] = json.loads(m_dict.get("metadata") or "{}")
            except Exception:
                m_dict["metadata"] = {}
            messages.append(m_dict)

        result = dict(row)
        result["messages"] = messages
        return result
    finally:
        conn.close()


@router.put("/{conv_id}")
def update_conversation(conv_id: str, req: UpdateConversationRequest) -> dict:
    conn = _get_db()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (req.title, now, conv_id),
        )
        if conn.total_changes == 0:
            raise HTTPException(status_code=404, detail="会话不存在")
        conn.commit()

        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conv_id,),
        )
        return dict(cur.fetchone())
    finally:
        conn.close()


@router.delete("/{conv_id}")
def delete_conversation(conv_id: str) -> dict:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        if conn.total_changes == 0:
            raise HTTPException(status_code=404, detail="会话不存在")
        conn.commit()
        return {"ok": True, "id": conv_id}
    finally:
        conn.close()


@router.post("/{conv_id}/messages")
def add_message(conv_id: str, req: AddMessageRequest) -> dict:
    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="会话不存在")

        mid = uuid.uuid4().hex
        now = datetime.now().isoformat()
        metadata = json.dumps(req.metadata or {}, ensure_ascii=False)

        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (mid, conv_id, req.role, req.content, metadata, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id)
        )
        conn.commit()

        return {
            "id": mid,
            "conversation_id": conv_id,
            "role": req.role,
            "content": req.content,
            "metadata": req.metadata or {},
            "created_at": now,
        }
    finally:
        conn.close()


@router.delete("/{conv_id}/messages/{msg_id}")
def delete_message(conv_id: str, msg_id: str) -> dict:
    conn = _get_db()
    try:
        conn.execute(
            "DELETE FROM messages WHERE id = ? AND conversation_id = ?", (msg_id, conv_id)
        )
        if conn.total_changes == 0:
            raise HTTPException(status_code=404, detail="消息不存在")
        conn.commit()
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id)
        )
        conn.commit()
        return {"ok": True, "id": msg_id}
    finally:
        conn.close()
