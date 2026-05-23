"""
股票分组管理 API 模块
提供股票分组的增删改查 CRUD 接口。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.db import connect, execute, executemany, load_mysql_config, query_dict
from core.data import get_watchlist
from core.jobs.domains.stock_group import ensure_stock_group_tables
from infra.storage.logging_service import get_logger

logger = get_logger("stock_group")

router = APIRouter(prefix="/api/v1/stock-groups", tags=["stock-groups"])


class CreateGroupRequest(BaseModel):
    name: str
    description: str = ""


class UpdateGroupRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class BatchAddItemsRequest(BaseModel):
    stock_codes: list[str]


def _ensure_tables() -> None:
    """确保分组表已创建"""
    try:
        ensure_stock_group_tables()
    except Exception as e:
        logger.error("建表失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"建表失败: {e}")


@router.get("")
def list_groups() -> dict[str, Any]:
    """
    获取所有股票分组列表，包含每个组的股票数量。
    """
    _ensure_tables()
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(
            conn,
            """
            SELECT g.id, g.name, g.description, g.created_at, g.updated_at,
                   COUNT(i.id) AS stock_count
            FROM trade_stock_group g
            LEFT JOIN trade_stock_group_item i ON i.group_id = g.id
            GROUP BY g.id
            ORDER BY g.id
            """,
        )
        items = []
        for r in rows:
            items.append({
                "id": int(r.get("id") or 0),
                "name": str(r.get("name") or ""),
                "description": str(r.get("description") or ""),
                "stock_count": int(r.get("stock_count") or 0),
                "created_at": str(r.get("created_at") or ""),
                "updated_at": str(r.get("updated_at") or ""),
            })
        return {"ok": True, "groups": items}
    finally:
        conn.close()


@router.get("/stock-count")
def stock_count() -> dict[str, Any]:
    """
    查询全市场股票数量（trade_stock_master 表记录总数）。
    """
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(conn, "SELECT COUNT(*) AS cnt FROM trade_stock_master")
        total = int((rows or [{}])[0].get("cnt") or 0)
        return {"ok": True, "total": total}
    finally:
        conn.close()


@router.get("/watchlist-codes")
def watchlist_codes() -> dict[str, Any]:
    """
    获取自选股中所有分组下的全部股票代码（去重）。
    """
    result = get_watchlist()
    items = result.get("items") or []
    # 提取 stock_code 并去重，保持顺序
    seen: set[str] = set()
    codes: list[str] = []
    for item in items:
        code = str(item.get("stock_code") or "").strip()
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return {"ok": True, "codes": codes}


@router.post("")
def create_group(body: CreateGroupRequest) -> dict[str, Any]:
    """
    创建新的股票分组。
    """
    _ensure_tables()
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="组名称不能为空")
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        gid = execute(
            conn,
            "INSERT INTO trade_stock_group (name, description) VALUES (%s, %s)",
            (name, body.description or ""),
        )
        # 获取自增ID
        with conn.cursor() as cur:
            cur.execute("SELECT LAST_INSERT_ID() AS gid")
            row = cur.fetchone()
            new_id = int(row["gid"]) if row else 0
        logger.info("创建股票分组", extra={"group_id": new_id, "group_name": name})
        return {"ok": True, "group": {"id": new_id, "name": name, "description": body.description or ""}}
    finally:
        conn.close()


@router.put("/{group_id}")
def update_group(group_id: int, body: UpdateGroupRequest) -> dict[str, Any]:
    """
    修改分组名称或描述。
    """
    _ensure_tables()
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        # 检查分组是否存在
        rows = query_dict(conn, "SELECT id FROM trade_stock_group WHERE id = %s", (group_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="分组不存在")

        updates: list[str] = []
        params: list[Any] = []
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="组名称不能为空")
            updates.append("name = %s")
            params.append(name)
        if body.description is not None:
            updates.append("description = %s")
            params.append(body.description)
        if not updates:
            return {"ok": True, "message": "无变更"}

        params.append(group_id)
        sql = "UPDATE trade_stock_group SET {} WHERE id = %s".format(", ".join(updates))
        execute(conn, sql, tuple(params))
        logger.info("更新股票分组", extra={"group_id": group_id})
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/{group_id}")
def delete_group(group_id: int) -> dict[str, Any]:
    """
    删除分组（级联删除组内所有股票）。
    """
    _ensure_tables()
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(conn, "SELECT id FROM trade_stock_group WHERE id = %s", (group_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="分组不存在")
        execute(conn, "DELETE FROM trade_stock_group WHERE id = %s", (group_id,))
        logger.info("删除股票分组", extra={"group_id": group_id})
        return {"ok": True}
    finally:
        conn.close()


@router.get("/{group_id}/items")
def list_group_items(group_id: int) -> dict[str, Any]:
    """
    获取分组内的股票列表。
    """
    _ensure_tables()
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(
            conn,
            """
            SELECT i.id, i.stock_code, i.stock_name, i.created_at
            FROM trade_stock_group_item i
            WHERE i.group_id = %s
            ORDER BY i.id
            """,
            (group_id,),
        )
        items = []
        for r in rows:
            items.append({
                "id": int(r.get("id") or 0),
                "stock_code": str(r.get("stock_code") or ""),
                "stock_name": str(r.get("stock_name") or ""),
                "created_at": str(r.get("created_at") or ""),
            })
        return {"ok": True, "items": items}
    finally:
        conn.close()


@router.post("/{group_id}/items")
def batch_add_items(group_id: int, body: BatchAddItemsRequest) -> dict[str, Any]:
    """
    批量添加股票到分组。
    """
    _ensure_tables()
    codes = body.stock_codes if isinstance(body.stock_codes, list) else []
    if not codes:
        raise HTTPException(status_code=400, detail="股票代码列表不能为空")

    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        # 检查分组是否存在
        rows = query_dict(conn, "SELECT id FROM trade_stock_group WHERE id = %s", (group_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="分组不存在")

        batch: list[tuple[Any, ...]] = []
        for code in codes:
            code_str = str(code or "").strip().upper()
            if code_str:
                batch.append((group_id, code_str, ""))

        if batch:
            executemany(
                conn,
                "INSERT IGNORE INTO trade_stock_group_item (group_id, stock_code, stock_name) VALUES (%s, %s, %s)",
                batch,
            )
        logger.info("批量添加股票到分组", extra={"group_id": group_id, "count": len(batch)})
        return {"ok": True, "added": len(batch)}
    finally:
        conn.close()


@router.delete("/{group_id}/items/{item_id}")
def delete_group_item(group_id: int, item_id: int) -> dict[str, Any]:
    """
    从分组中删除某只股票。
    """
    _ensure_tables()
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        execute(
            conn,
            "DELETE FROM trade_stock_group_item WHERE id = %s AND group_id = %s",
            (item_id, group_id),
        )
        return {"ok": True}
    finally:
        conn.close()
