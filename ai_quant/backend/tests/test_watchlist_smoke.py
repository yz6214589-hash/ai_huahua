"""
自选股信息获取策略 冒烟测试

覆盖三个核心模块：
  1. 自选股列表获取 - GET /api/v1/watchlist
  2. 自选股行情快照获取 - GET /api/v1/watchlist/snapshots
  3. 自选股分组信息获取 - GET/POST/PUT/DELETE /api/v1/watchlist/groups
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app import app


def _unwrap(resp):
    body = resp.json()
    if isinstance(body, dict) and "success" in body and "data" in body:
        return body.get("data"), body
    return body, body


# ============================================================
# 模块1：自选股列表获取
# ============================================================

class TestWatchlistListRetrieval:
    """自选股列表获取策略冒烟测试"""

    def test_get_watchlist_returns_200_and_items(self):
        """冒烟：GET /api/v1/watchlist 返回 200，包含 items 字段"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist")
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_watchlist_items_have_required_fields(self):
        """冒烟：自选股列表中每只股票包含必填字段"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist")
        data, _ = _unwrap(resp)
        items = data.get("items") or []
        if items:
            required = {"stock_code", "stock_name", "pinned", "sortOrder"}
            for item in items:
                missing = required - set(item.keys())
                assert not missing, f"股票 {item.get('stock_code')} 缺少字段: {missing}"

    def test_get_watchlist_max_field_exists(self):
        """冒烟：自选股列表返回 max 字段（最大数量限制）"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist")
        data, _ = _unwrap(resp)
        assert "max" in data
        assert isinstance(data["max"], int)

    def test_add_watchlist_item_with_valid_code(self):
        """冒烟：POST /api/v1/watchlist 添加有效股票代码返回正确结构"""
        client = TestClient(app)
        resp = client.post("/api/v1/watchlist", json={"stock_code": "600519.SH"})
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert "ok" in data

    def test_add_watchlist_item_with_empty_code(self):
        """冒烟：POST /api/v1/watchlist 添加空代码不会导致服务崩溃"""
        client = TestClient(app)
        resp = client.post("/api/v1/watchlist", json={"stock_code": ""})
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True

    def test_delete_watchlist_item_returns_200(self):
        """冒烟：DELETE /api/v1/watchlist/{code} 删除自选股返回 200"""
        client = TestClient(app)
        resp = client.delete("/api/v1/watchlist/600519.SH")
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert "ok" in data

    def test_pin_watchlist_item_returns_200(self):
        """冒烟：PUT /api/v1/watchlist/{code}/pin 置顶操作返回 200"""
        client = TestClient(app)
        resp = client.put("/api/v1/watchlist/600519.SH/pin", json={"pinned": True})
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert "ok" in data

    def test_unpin_watchlist_item_returns_200(self):
        """冒烟：PUT /api/v1/watchlist/{code}/pin 取消置顶返回 200"""
        client = TestClient(app)
        resp = client.put("/api/v1/watchlist/600519.SH/pin", json={"pinned": False})
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert "ok" in data

    def test_reorder_watchlist_returns_200(self):
        """冒烟：PATCH /api/v1/watchlist/reorder 排序操作返回 200"""
        client = TestClient(app)
        resp = client.patch("/api/v1/watchlist/reorder", json={"codes": ["600519.SH"]})
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True

    def test_watchlist_return_order_pinned_first(self):
        """冒烟：自选股列表排序策略验证 - 置顶股票排在前面"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist")
        data, _ = _unwrap(resp)
        items = data.get("items") or []
        pinned_items = [i for i in items if i.get("pinned")]
        unpinned_items = [i for i in items if not i.get("pinned")]
        for pin_item in pinned_items:
            pin_idx = items.index(pin_item)
            for unpin_item in unpinned_items:
                unpin_idx = items.index(unpin_item)
                assert pin_idx < unpin_idx, (
                    f"置顶股票 {pin_item.get('stock_code')} 应排在非置顶股票 {unpin_item.get('stock_code')} 前面"
                )


# ============================================================
# 模块2：自选股行情快照获取
# ============================================================

class TestWatchlistSnapshotsRetrieval:
    """自选股行情快照获取策略冒烟测试"""

    def test_get_snapshots_returns_200_and_items(self):
        """冒烟：GET /api/v1/watchlist/snapshots 返回 200，包含 items 列表"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist/snapshots")
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_snapshots_items_have_required_fields(self):
        """冒烟：快照中每只股票包含行情必填字段"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist/snapshots")
        data, _ = _unwrap(resp)
        items = data.get("items") or []
        if items:
            required = {"stock_code", "price", "change", "pctChange", "trade_date", "source"}
            for item in items:
                missing = required - set(item.keys())
                assert not missing, f"快照股票 {item.get('stock_code')} 缺少字段: {missing}"

    def test_snapshots_source_field_is_daily(self):
        """冒烟：快照数据源字段 source 固定为 daily"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist/snapshots")
        data, _ = _unwrap(resp)
        items = data.get("items") or []
        for item in items:
            assert item.get("source") == "daily", (
                f"快照股票 {item.get('stock_code')} 的 source 应为 'daily'，实际为 {item.get('source')}"
            )

    def test_snapshots_pct_change_is_percentage(self):
        """冒烟：涨跌幅 pctChange 为百分比数值（如有数据）"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist/snapshots")
        data, _ = _unwrap(resp)
        items = data.get("items") or []
        for item in items:
            pct = item.get("pctChange")
            if pct is not None:
                assert isinstance(pct, (int, float)), f"pctChange 应为数值，实际为 {type(pct)}"

    def test_snapshots_stock_code_is_string(self):
        """冒烟：快照中 stock_code 字段为字符串类型"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist/snapshots")
        data, _ = _unwrap(resp)
        items = data.get("items") or []
        for item in items:
            assert isinstance(item.get("stock_code"), str), (
                f"stock_code 应为字符串，实际为 {type(item.get('stock_code'))}"
            )


# ============================================================
# 模块3：自选股分组信息获取
# ============================================================

class TestWatchlistGroupsRetrieval:
    """自选股分组信息获取策略冒烟测试"""

    def test_get_groups_returns_200_and_items(self):
        """冒烟：GET /api/v1/watchlist/groups 返回 200，包含 items 列表"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist/groups")
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_groups_items_have_required_fields(self):
        """冒烟：分组列表中每个分组包含必填字段"""
        client = TestClient(app)
        resp = client.get("/api/v1/watchlist/groups")
        data, _ = _unwrap(resp)
        items = data.get("items") or []
        if items:
            required = {"id", "name", "sort_order"}
            for item in items:
                missing = required - set(item.keys())
                assert not missing, f"分组 {item.get('name')} 缺少字段: {missing}"

    def test_create_group_returns_new_group(self):
        """冒烟：POST /api/v1/watchlist/groups 创建分组返回新建分组信息"""
        client = TestClient(app)
        resp = client.post("/api/v1/watchlist/groups", json={"name": "冒烟测试分组"})
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert "id" in data
        assert data.get("name") == "冒烟测试分组"
        # 清理
        group_id = data.get("id")
        if group_id:
            client.delete(f"/api/v1/watchlist/groups/{group_id}")

    def test_create_group_with_empty_name(self):
        """冒烟：POST /api/v1/watchlist/groups 空名称不导致服务崩溃"""
        client = TestClient(app)
        resp = client.post("/api/v1/watchlist/groups", json={"name": ""})
        assert resp.status_code in (200, 400, 422)

    def test_rename_group_returns_200(self):
        """冒烟：PUT /api/v1/watchlist/groups/{id}/rename 重命名分组返回 200"""
        client = TestClient(app)
        create_resp = client.post("/api/v1/watchlist/groups", json={"name": "待重命名分组"})
        data, _ = _unwrap(create_resp)
        group_id = data.get("id")
        if not group_id:
            return
        try:
            rename_resp = client.put(
                f"/api/v1/watchlist/groups/{group_id}/rename",
                json={"name": "已重命名分组"},
            )
            assert rename_resp.status_code == 200
            data2, body2 = _unwrap(rename_resp)
            assert body2.get("success") is True
            assert data2.get("ok") is True
        finally:
            client.delete(f"/api/v1/watchlist/groups/{group_id}")

    def test_delete_group_returns_200(self):
        """冒烟：DELETE /api/v1/watchlist/groups/{id} 删除分组返回 200"""
        client = TestClient(app)
        create_resp = client.post("/api/v1/watchlist/groups", json={"name": "待删除分组"})
        data, _ = _unwrap(create_resp)
        group_id = data.get("id")
        if not group_id:
            return
        delete_resp = client.delete(f"/api/v1/watchlist/groups/{group_id}")
        assert delete_resp.status_code == 200
        data2, body2 = _unwrap(delete_resp)
        assert body2.get("success") is True
        assert data2.get("ok") is True

    def test_add_watchlist_with_groups_returns_200(self):
        """冒烟：POST /api/v1/watchlist/with-groups 添加自选股并关联分组返回 200"""
        client = TestClient(app)
        resp = client.post(
            "/api/v1/watchlist/with-groups",
            json={"stock_code": "600519.SH", "group_ids": []},
        )
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert data.get("ok") is True

    def test_watchlist_codes_from_stock_group(self):
        """冒烟：GET /api/v1/stock-groups/watchlist-codes 获取自选股代码列表"""
        client = TestClient(app)
        resp = client.get("/api/v1/stock-groups/watchlist-codes")
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True
        assert "codes" in data
        assert isinstance(data["codes"], list)


# ============================================================
# 模块4：股票搜索（自选股关联功能）
# ============================================================

class TestStockSearch:
    """股票搜索功能冒烟测试（与自选股添加关联）"""

    def test_search_stocks_returns_200(self):
        """冒烟：GET /api/v1/stocks 搜索股票返回 200"""
        client = TestClient(app)
        resp = client.get("/api/v1/stocks?q=茅台")
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True

    def test_search_stocks_with_empty_query(self):
        """冒烟：GET /api/v1/stocks 空查询不导致服务崩溃"""
        client = TestClient(app)
        resp = client.get("/api/v1/stocks?q=")
        assert resp.status_code == 200
        data, body = _unwrap(resp)
        assert body.get("success") is True