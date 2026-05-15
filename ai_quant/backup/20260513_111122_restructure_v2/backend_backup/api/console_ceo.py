from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from modules.console import get_overview, get_status, trigger_morning

router = APIRouter(prefix="/api/v1/console", tags=["console"])


@router.get("/status")
def console_status() -> dict[str, object]:
    return get_status()


@router.get("/overview")
def console_overview() -> dict[str, object]:
    return get_overview()


@router.post("/morning/trigger")
def console_trigger_morning(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return trigger_morning(body)
    except Exception as exc:
        msg = str(exc).strip()
        lower = msg.lower()
        # 屏蔽数据库内部错误细节，统一返回可读提示
        if any(x in lower for x in ("table", "mysql", "sql", "traceback", "operationalerror", "programmingerror")):
            raise HTTPException(status_code=500, detail="数据库数据暂不可用，请先完成采集后重试")
        raise HTTPException(status_code=500, detail=msg or "晨会简报生成失败，请稍后重试")
