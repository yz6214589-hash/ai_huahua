"""
会话 Repository - 封装会话和消息的数据访问操作
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from core.repository.base import BaseRepository


class ConversationRepository(BaseRepository):
    """会话数据访问层，封装conversations和messages表的CRUD操作"""

    def list_conversations(self) -> list[dict]:
        """查询所有会话，按更新时间倒序排列"""
        return self._query(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        )

    def create_conversation(self, title: str = "新对话") -> dict:
        """创建新会话，返回会话dict"""
        cid = uuid.uuid4().hex
        now = datetime.now().isoformat()

        self._execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (%s, %s, %s, %s)",
            (cid, title, now, now),
        )

        return {"id": cid, "title": title, "created_at": now, "updated_at": now}

    def get_conversation(self, conv_id: str) -> dict | None:
        """获取会话详情，包含消息列表；不存在时返回None"""
        conv = self._query_one(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = %s",
            (conv_id,),
        )
        if not conv:
            return None

        result = dict(conv)

        msg_rows = self._query(
            "SELECT id, role, content, metadata, created_at FROM messages "
            "WHERE conversation_id = %s ORDER BY created_at ASC",
            (conv_id,),
        )

        messages = []
        for m in msg_rows:
            try:
                m["metadata"] = json.loads(m.get("metadata") or "{}")
            except Exception:
                m["metadata"] = {}
            messages.append(m)

        result["messages"] = messages
        return result

    def update_conversation(self, conv_id: str, title: str) -> dict | None:
        """更新会话标题，返回更新后的会话dict；不存在时返回None"""
        now = datetime.now().isoformat()
        affected = self._execute(
            "UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s",
            (title, now, conv_id),
        )
        if affected == 0:
            return None

        return self._query_one(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = %s",
            (conv_id,),
        )

    def delete_conversation(self, conv_id: str) -> bool:
        """删除会话及关联消息，返回是否成功"""
        self._execute("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))
        affected = self._execute(
            "DELETE FROM conversations WHERE id = %s", (conv_id,)
        )
        return affected > 0

    def add_message(
        self, conv_id: str, role: str, content: str, metadata: dict | None = None
    ) -> dict | None:
        """向会话添加消息，返回消息dict；会话不存在时返回None"""
        existing = self._query_one(
            "SELECT id FROM conversations WHERE id = %s", (conv_id,)
        )
        if not existing:
            return None

        mid = uuid.uuid4().hex
        now = datetime.now().isoformat()
        metadata_str = json.dumps(metadata or {}, ensure_ascii=False)

        self._execute(
            "INSERT INTO messages (id, conversation_id, role, content, metadata, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (mid, conv_id, role, content, metadata_str, now),
        )
        self._execute(
            "UPDATE conversations SET updated_at = %s WHERE id = %s",
            (now, conv_id),
        )

        return {
            "id": mid,
            "conversation_id": conv_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "created_at": now,
        }

    def delete_message(self, conv_id: str, msg_id: str) -> bool:
        """删除消息，返回是否成功"""
        affected = self._execute(
            "DELETE FROM messages WHERE id = %s AND conversation_id = %s",
            (msg_id, conv_id),
        )
        if affected == 0:
            return False

        now = datetime.now().isoformat()
        self._execute(
            "UPDATE conversations SET updated_at = %s WHERE id = %s",
            (now, conv_id),
        )
        return True
