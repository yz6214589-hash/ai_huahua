"""
自选股 Repository - 封装自选股数据访问操作
"""
from __future__ import annotations

from core.repository.base import BaseRepository


class WatchlistRepository(BaseRepository):
    """自选股数据访问层，封装watchlist和watchlist_groups表的CRUD操作"""

    def list_watchlist(self) -> list[dict]:
        """查询所有自选股，按置顶和排序字段排列"""
        return self._query(
            "SELECT id, stock_code, stock_name, pinned, sort_order, group_id, "
            "created_at, updated_at FROM watchlist ORDER BY pinned DESC, sort_order ASC"
        )

    def add_item(self, stock_code: str) -> dict:
        """添加自选股，返回自选股dict"""
        from datetime import datetime
        now = datetime.now().isoformat()

        self._execute(
            "INSERT INTO watchlist (stock_code, created_at, updated_at) VALUES (%s, %s, %s)",
            (stock_code, now, now),
        )

        return {"stock_code": stock_code, "created_at": now}

    def delete_item(self, stock_code: str) -> bool:
        """删除自选股，返回是否成功"""
        affected = self._execute(
            "DELETE FROM watchlist WHERE stock_code = %s", (stock_code,)
        )
        return affected > 0

    def pin_item(self, stock_code: str, pinned: bool) -> dict:
        """设置自选股置顶状态"""
        from datetime import datetime
        now = datetime.now().isoformat()
        self._execute(
            "UPDATE watchlist SET pinned = %s, updated_at = %s WHERE stock_code = %s",
            (1 if pinned else 0, now, stock_code),
        )
        return {"stock_code": stock_code, "pinned": pinned}

    def reorder_items(self, codes: list[str]) -> dict:
        """更新自选股排序"""
        from datetime import datetime
        now = datetime.now().isoformat()
        for idx, code in enumerate(codes):
            self._execute(
                "UPDATE watchlist SET sort_order = %s, updated_at = %s WHERE stock_code = %s",
                (idx, now, code),
            )
        return {"ok": True}

    def list_groups(self) -> list[dict]:
        """查询所有自选股分组"""
        return self._query(
            "SELECT id, name, created_at, updated_at FROM watchlist_groups ORDER BY id ASC"
        )

    def create_group(self, name: str) -> dict:
        """创建自选股分组"""
        from datetime import datetime
        now = datetime.now().isoformat()
        self._execute(
            "INSERT INTO watchlist_groups (name, created_at, updated_at) VALUES (%s, %s, %s)",
            (name, now, now),
        )
        return {"name": name}

    def rename_group(self, group_id: int, name: str) -> dict:
        """重命名自选股分组"""
        from datetime import datetime
        now = datetime.now().isoformat()
        affected = self._execute(
            "UPDATE watchlist_groups SET name = %s, updated_at = %s WHERE id = %s",
            (name, now, group_id),
        )
        if affected == 0:
            return {"error": "分组不存在"}
        return {"id": group_id, "name": name}

    def delete_group(self, group_id: int) -> bool:
        """删除自选股分组"""
        affected = self._execute(
            "DELETE FROM watchlist_groups WHERE id = %s", (group_id,)
        )
        return affected > 0

    def add_item_with_groups(self, stock_code: str, group_ids: list[int]) -> dict:
        """添加自选股并关联分组"""
        from datetime import datetime
        now = datetime.now().isoformat()

        self._execute(
            "INSERT INTO watchlist (stock_code, created_at, updated_at) VALUES (%s, %s, %s)",
            (stock_code, now, now),
        )

        for gid in group_ids:
            self._execute(
                "INSERT INTO watchlist_item_groups (stock_code, group_id) VALUES (%s, %s)",
                (stock_code, gid),
            )

        return {"stock_code": stock_code, "group_ids": group_ids}

    def get_by_group(self, group_id: int) -> list[dict]:
        """按分组查询自选股"""
        return self._query(
            "SELECT w.id, w.stock_code, w.stock_name, w.pinned, w.sort_order "
            "FROM watchlist w "
            "INNER JOIN watchlist_item_groups wig ON w.stock_code = wig.stock_code "
            "WHERE wig.group_id = %s "
            "ORDER BY w.pinned DESC, w.sort_order ASC",
            (group_id,),
        )

    def search_stocks(self, keyword: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """搜索股票"""
        # 使用stock_basic_info表作为股票基础信息查询源
        like_pattern = f"%{keyword}%"
        return self._query(
            "SELECT code, name, market, industry FROM stock_basic_info "
            "WHERE code LIKE %s OR name LIKE %s "
            "ORDER BY code ASC LIMIT %s OFFSET %s",
            (like_pattern, like_pattern, limit, offset),
        )
