from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from modules.data import (
    add_watchlist_item,
    add_watchlist_item_with_groups,
    create_watchlist_group,
    delete_watchlist_item,
    delete_watchlist_group,
    get_watchlist,
    get_watchlist_by_group,
    get_watchlist_groups,
    get_watchlist_snapshots,
    pin_watchlist_item,
    reorder_watchlist,
    rename_watchlist_group,
    search_stocks,
)
from runtime.logging_service import get_logger

logger = get_logger("watchlist")

router = APIRouter(prefix="/api/v1", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    stock_code: str


class WatchlistPinRequest(BaseModel):
    pinned: bool


class WatchlistReorderRequest(BaseModel):
    codes: list[str]


class GroupCreateRequest(BaseModel):
    name: str


class GroupRenameRequest(BaseModel):
    name: str


class WatchlistAddWithGroupsRequest(BaseModel):
    stock_code: str
    group_ids: list[int] = []



@router.get("/watchlist")
def watchlist_get() -> dict[str, object]:
    logger.info("自选股列表查询", extra={})
    return get_watchlist()


@router.post("/watchlist")
def watchlist_add(req: WatchlistAddRequest) -> dict[str, Any]:
    logger.info("添加自选股", extra={
        "stock_code": req.stock_code
    })
    result = add_watchlist_item(req.stock_code)
    logger.info("添加自选股成功", extra={
        "stock_code": req.stock_code
    })
    return result


@router.delete("/watchlist/{stock_code}")
def watchlist_delete(stock_code: str) -> dict[str, Any]:
    logger.info("删除自选股", extra={
        "stock_code": stock_code
    })
    result = delete_watchlist_item(stock_code)
    logger.info("删除自选股成功", extra={
        "stock_code": stock_code
    })
    return result


@router.put("/watchlist/{stock_code}/pin")
def watchlist_pin(stock_code: str, req: WatchlistPinRequest) -> dict[str, Any]:
    logger.info("自选股置顶操作", extra={
        "stock_code": stock_code,
        "pinned": req.pinned
    })
    return pin_watchlist_item(stock_code, bool(req.pinned))


@router.put("/watchlist/reorder")
def watchlist_reorder(req: WatchlistReorderRequest) -> dict[str, Any]:
    logger.info("自选股排序更新", extra={
        "count": len(req.codes)
    })
    return reorder_watchlist(req.codes)


@router.get("/watchlist/snapshots")
def watchlist_snapshots() -> dict[str, Any]:
    logger.info("自选股行情快照查询", extra={})
    return get_watchlist_snapshots()


@router.get("/watchlist/groups")
def watchlist_groups_get() -> dict[str, Any]:
    logger.info("自选股分组列表查询", extra={})
    return get_watchlist_groups()


@router.post("/watchlist/groups")
def watchlist_group_create(req: GroupCreateRequest) -> dict[str, Any]:
    logger.info("新建自选股分组", extra={"group_name": req.name})
    return create_watchlist_group(req.name)


@router.put("/watchlist/groups/{group_id}/rename")
def watchlist_group_rename(group_id: int, req: GroupRenameRequest) -> dict[str, Any]:
    logger.info("重命名自选股分组", extra={"group_id": group_id, "group_name": req.name})
    return rename_watchlist_group(group_id, req.name)


@router.delete("/watchlist/groups/{group_id}")
def watchlist_group_delete(group_id: int) -> dict[str, Any]:
    logger.info("删除自选股分组", extra={"group_id": group_id})
    return delete_watchlist_group(group_id)


@router.get("/watchlist/list")
def watchlist_list_by_group(group_id: int | None = None) -> dict[str, Any]:
    logger.info("按分组查询自选股", extra={"group_id": group_id})
    return get_watchlist_by_group(group_id)


@router.post("/watchlist/with-groups")
def watchlist_add_with_groups(req: WatchlistAddWithGroupsRequest) -> dict[str, Any]:
    logger.info("添加自选股（带分组）", extra={"stock_code": req.stock_code, "group_ids": req.group_ids})
    return add_watchlist_item_with_groups(req.stock_code, req.group_ids)



@router.get("/stocks")
def stocks_search(
    q: str = Query(default=""),
    limit: int = Query(default=20),
    offset: int = Query(default=0),
) -> dict[str, object]:
    logger.info("股票搜索", extra={
        "query": q,
        "limit": limit,
        "offset": offset,
    })
    return search_stocks(q=q, limit=limit, offset=offset)
