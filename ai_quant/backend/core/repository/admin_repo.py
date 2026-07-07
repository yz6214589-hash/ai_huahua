"""
管理后台 Repository - 封装管理后台数据访问操作
"""
from __future__ import annotations

import json

from core.repository.base import BaseRepository


class AdminRepository(BaseRepository):
    """管理后台数据访问层，封装会话统计、详情等操作"""

    def list_conversations(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """分页查询会话列表（含消息数和最后消息时间），返回(列表, 总数)"""
        where_clauses = []
        params: list = []

        if search:
            where_clauses.append("c.title LIKE %s")
            params.append(f"%{search}%")

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # 获取总数
        count_rows = self._query(
            f"SELECT COUNT(*) AS cnt FROM conversations c {where_sql}",
            tuple(params),
        )
        total = count_rows[0]["cnt"]

        # 获取分页数据
        offset = (page - 1) * page_size
        query_params = list(params) + [page_size, offset]
        rows = self._query(
            f"""
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count,
                   (SELECT MAX(m2.created_at) FROM messages m2 WHERE m2.conversation_id = c.id) AS last_message_time
            FROM conversations c
            {where_sql}
            ORDER BY c.updated_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(query_params),
        )

        return rows, total

    def conversation_stats(self) -> dict:
        """获取会话统计数据"""
        total_rows = self._query("SELECT COUNT(*) AS cnt FROM conversations")
        total = total_rows[0]["cnt"]

        msg_rows = self._query("SELECT COUNT(*) AS cnt FROM messages")
        total_messages = msg_rows[0]["cnt"]

        sys_rows = self._query(
            "SELECT COUNT(*) AS cnt FROM conversations WHERE id NOT LIKE %s",
            ("feishu_%",),
        )
        system_count = sys_rows[0]["cnt"]

        feishu_rows = self._query(
            "SELECT COUNT(*) AS cnt FROM conversations WHERE id LIKE %s",
            ("feishu_%",),
        )
        feishu_total = feishu_rows[0]["cnt"]

        return {
            "total_conversations": total,
            "total_messages": total_messages,
            "feishu_private": feishu_total,
            "feishu_group": 0,
            "system": system_count,
        }

    def get_conversation_detail(
        self, conv_id: str, page: int = 1, page_size: int = 50
    ) -> dict | None:
        """获取会话详情（含分页消息列表），不存在时返回None"""
        conv = self._query_one(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = %s",
            (conv_id,),
        )
        if not conv:
            return None

        conv = dict(conv)

        # 获取消息总数
        count_rows = self._query(
            "SELECT COUNT(*) AS cnt FROM messages WHERE conversation_id = %s",
            (conv_id,),
        )
        total_messages = count_rows[0]["cnt"]

        # 获取分页消息
        offset = (page - 1) * page_size
        msg_rows = self._query(
            "SELECT id, role, content, metadata, created_at FROM messages "
            "WHERE conversation_id = %s ORDER BY created_at ASC LIMIT %s OFFSET %s",
            (conv_id, page_size, offset),
        )

        messages = []
        for m in msg_rows:
            try:
                m["metadata"] = json.loads(m.get("metadata") or "{}")
            except Exception:
                m["metadata"] = {}
            messages.append(m)

        conv["messages"] = messages
        conv["messages_total"] = total_messages
        conv["messages_page"] = page
        conv["messages_page_size"] = page_size
        return conv

    def update_conversation_title(self, conv_id: str, new_title: str) -> str | None:
        """更新会话标题，返回错误信息或None表示成功"""
        from datetime import datetime

        existing = self._query_one(
            "SELECT id FROM conversations WHERE id = %s", (conv_id,)
        )
        if not existing:
            return "会话不存在"

        now = datetime.now().isoformat()
        self._execute(
            "UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s",
            (new_title, now, conv_id),
        )
        return None
