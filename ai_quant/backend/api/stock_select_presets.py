"""
选股条件预设管理API模块
提供选股条件的保存、加载、修改和删除功能
"""

from __future__ import annotations

import json
from typing import Any

import pymysql
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.db import connect, load_mysql_config, query_dict, execute
from infra.storage.logging_service import get_logger

logger = get_logger("stock_select_presets")

router = APIRouter(prefix="/api/v1/stock-select/presets", tags=["stock-select-presets"])


class PresetCreate(BaseModel):
    name: str
    filters: dict[str, Any]
    disabled_filters: list[str] | None = None
    disabled_boundaries: dict[str, dict[str, bool]] | None = None
    exclude_types: list[str] | None = None
    industries: list[str] | None = None


class PresetUpdate(BaseModel):
    name: str | None = None
    filters: dict[str, Any] | None = None
    disabled_filters: list[str] | None = None
    disabled_boundaries: dict[str, dict[str, bool]] | None = None
    exclude_types: list[str] | None = None
    industries: list[str] | None = None


def _create_direct_connection(cfg):
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=5,
        read_timeout=15,
        write_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )


def init_presets_table():
    cfg = load_mysql_config()
    conn = _create_direct_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trade_stock_select_presets (
                  id          INT AUTO_INCREMENT PRIMARY KEY  COMMENT '主键ID',
                  name        VARCHAR(50) NOT NULL             COMMENT '条件名称',
                  filters     JSON NOT NULL                    COMMENT '筛选条件JSON（filterValues）',
                  disabled_filters JSON DEFAULT NULL           COMMENT '禁用的指标列表',
                  disabled_boundaries JSON DEFAULT NULL        COMMENT '指标上下限禁用状态',
                  exclude_types   JSON DEFAULT NULL            COMMENT '排除股票类型',
                  industries      JSON DEFAULT NULL            COMMENT '行业筛选列表',
                  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                  updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='选股条件预设表'
            """)
            try:
                cur.execute("ALTER TABLE trade_stock_select_presets ADD COLUMN disabled_boundaries JSON DEFAULT NULL COMMENT '指标上下限禁用状态' AFTER disabled_filters")
            except Exception:
                pass
        logger.info("选股条件预设表初始化完成")
    except Exception as e:
        logger.warning("选股条件预设表初始化失败", extra={"error": str(e)})
    finally:
        conn.close()


@router.get("")
def list_presets() -> list[dict[str, Any]]:
    cfg = load_mysql_config()
    conn = _create_direct_connection(cfg)
    try:
        rows = query_dict(conn, """
            SELECT id, name, filters, disabled_filters, disabled_boundaries, exclude_types, industries, created_at, updated_at
            FROM trade_stock_select_presets
            ORDER BY created_at DESC
        """)
        result = []
        for row in rows:
            item = {
                "id": row["id"],
                "name": row["name"],
                "filters": json.loads(row["filters"]) if isinstance(row["filters"], str) else (row["filters"] or {}),
                "disabled_filters": json.loads(row["disabled_filters"]) if isinstance(row["disabled_filters"], str) else (row["disabled_filters"] or []),
                "disabled_boundaries": json.loads(row["disabled_boundaries"]) if isinstance(row["disabled_boundaries"], str) else (row["disabled_boundaries"] or {}),
                "exclude_types": json.loads(row["exclude_types"]) if isinstance(row["exclude_types"], str) else (row["exclude_types"] or []),
                "industries": json.loads(row["industries"]) if isinstance(row["industries"], str) else (row["industries"] or []),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            }
            result.append(item)
        return result
    except Exception as e:
        logger.error("获取条件列表失败", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"获取条件列表失败: {str(e)}")
    finally:
        conn.close()


@router.post("")
def create_preset(body: PresetCreate) -> dict[str, Any]:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="条件名称不能为空")
    if len(name) > 50:
        raise HTTPException(status_code=400, detail="条件名称不能超过50个字符")

    cfg = load_mysql_config()
    conn = _create_direct_connection(cfg)
    try:
        filters_json = json.dumps(body.filters, ensure_ascii=False)
        disabled_json = json.dumps(body.disabled_filters or [], ensure_ascii=False)
        disabled_boundaries_json = json.dumps(body.disabled_boundaries or {}, ensure_ascii=False)
        exclude_json = json.dumps(body.exclude_types or [], ensure_ascii=False)
        industries_json = json.dumps(body.industries or [], ensure_ascii=False)

        rowcount = execute(conn, """
            INSERT INTO trade_stock_select_presets (name, filters, disabled_filters, disabled_boundaries, exclude_types, industries)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, filters_json, disabled_json, disabled_boundaries_json, exclude_json, industries_json))

        if rowcount == 0:
            raise HTTPException(status_code=500, detail="保存条件失败")

        rows = query_dict(conn, "SELECT LAST_INSERT_ID() as id")
        new_id = rows[0]["id"] if rows else None

        logger.info("选股条件保存成功", extra={"preset_name": name, "id": new_id})
        return {
            "id": new_id,
            "name": name,
            "filters": body.filters,
            "disabled_filters": body.disabled_filters or [],
            "disabled_boundaries": body.disabled_boundaries or {},
            "exclude_types": body.exclude_types or [],
            "industries": body.industries or [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("保存条件失败", extra={"error": str(e), "preset_name": name})
        raise HTTPException(status_code=500, detail=f"保存条件失败: {str(e)}")
    finally:
        conn.close()


@router.put("/{preset_id}")
def update_preset(preset_id: int, body: PresetUpdate) -> dict[str, Any]:
    cfg = load_mysql_config()
    conn = _create_direct_connection(cfg)
    try:
        rows = query_dict(conn, "SELECT id FROM trade_stock_select_presets WHERE id = %s", (preset_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="条件不存在")

        update_fields = []
        update_values = []

        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="条件名称不能为空")
            if len(name) > 50:
                raise HTTPException(status_code=400, detail="条件名称不能超过50个字符")
            update_fields.append("name = %s")
            update_values.append(name)

        if body.filters is not None:
            update_fields.append("filters = %s")
            update_values.append(json.dumps(body.filters, ensure_ascii=False))

        if body.disabled_filters is not None:
            update_fields.append("disabled_filters = %s")
            update_values.append(json.dumps(body.disabled_filters, ensure_ascii=False))

        if body.disabled_boundaries is not None:
            update_fields.append("disabled_boundaries = %s")
            update_values.append(json.dumps(body.disabled_boundaries, ensure_ascii=False))

        if body.exclude_types is not None:
            update_fields.append("exclude_types = %s")
            update_values.append(json.dumps(body.exclude_types, ensure_ascii=False))

        if body.industries is not None:
            update_fields.append("industries = %s")
            update_values.append(json.dumps(body.industries, ensure_ascii=False))

        if not update_fields:
            raise HTTPException(status_code=400, detail="没有需要更新的字段")

        update_values.append(preset_id)
        execute(conn, f"UPDATE trade_stock_select_presets SET {', '.join(update_fields)} WHERE id = %s", tuple(update_values))

        rows = query_dict(conn, """
            SELECT id, name, filters, disabled_filters, disabled_boundaries, exclude_types, industries, created_at, updated_at
            FROM trade_stock_select_presets WHERE id = %s
        """, (preset_id,))

        if not rows:
            raise HTTPException(status_code=404, detail="条件不存在")

        row = rows[0]
        logger.info("选股条件更新成功", extra={"id": preset_id, "preset_name": row["name"]})
        return {
            "id": row["id"],
            "name": row["name"],
            "filters": json.loads(row["filters"]) if isinstance(row["filters"], str) else (row["filters"] or {}),
            "disabled_filters": json.loads(row["disabled_filters"]) if isinstance(row["disabled_filters"], str) else (row["disabled_filters"] or []),
            "disabled_boundaries": json.loads(row["disabled_boundaries"]) if isinstance(row["disabled_boundaries"], str) else (row["disabled_boundaries"] or {}),
            "exclude_types": json.loads(row["exclude_types"]) if isinstance(row["exclude_types"], str) else (row["exclude_types"] or []),
            "industries": json.loads(row["industries"]) if isinstance(row["industries"], str) else (row["industries"] or []),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新条件失败", extra={"error": str(e), "id": preset_id})
        raise HTTPException(status_code=500, detail=f"更新条件失败: {str(e)}")
    finally:
        conn.close()


@router.delete("/{preset_id}")
def delete_preset(preset_id: int) -> dict[str, bool]:
    cfg = load_mysql_config()
    conn = _create_direct_connection(cfg)
    try:
        rows = query_dict(conn, "SELECT id FROM trade_stock_select_presets WHERE id = %s", (preset_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="条件不存在")

        execute(conn, "DELETE FROM trade_stock_select_presets WHERE id = %s", (preset_id,))
        logger.info("选股条件删除成功", extra={"id": preset_id})
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除条件失败", extra={"error": str(e), "id": preset_id})
        raise HTTPException(status_code=500, detail=f"删除条件失败: {str(e)}")
    finally:
        conn.close()
