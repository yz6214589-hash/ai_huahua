"""
主力识别API接口
提供单股主力行为分析功能
"""

from fastapi import APIRouter, HTTPException
from typing import Any

from core.mainforce.engine import MainForceEngine, TIME_RANGE_PRESETS
from infra.storage.logging_service import get_logger

logger = get_logger("mainforce")

router = APIRouter(prefix="/api/v1/mainforce", tags=["主力识别"])


# ============ 单股分析API ============

@router.post("/analyze")
async def analyze_stock(body: dict):
    """
    触发单只股票的主力行为分析

    请求体参数:
        stock_code (str): 股票代码，如 "000001.SZ"
        time_range (str): 时间范围，可选值: today / yesterday / last_5_days

    返回:
        完整的主力行为分析结果
    """
    stock_code = body.get("stock_code", "").strip()
    time_range = body.get("time_range", "today").strip()

    if not stock_code:
        raise HTTPException(status_code=400, detail="stock_code is required")

    if time_range not in TIME_RANGE_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"time_range must be one of {list(TIME_RANGE_PRESETS.keys())}",
        )

    logger.info("收到主力行为分析请求", extra={
        "stock_code": stock_code,
        "time_range": time_range,
    })

    try:
        engine = MainForceEngine()
        result = engine.analyze_stock(stock_code, time_range=time_range)

        if "error" in result:
            logger.warning("分析未完成", extra={
                "stock_code": stock_code,
                "error": result.get("error"),
            })
            return result

        try:
            activity_id = engine.save_analysis_result(result)
            result["activity_id"] = activity_id
        except Exception as save_err:
            logger.warning("保存活动记录失败，不影响分析结果", extra={"error": str(save_err)})

        try:
            task_id = engine.save_task_record(stock_code, time_range, result)
            result["task_id"] = task_id
        except Exception as save_err:
            logger.warning("保存任务记录失败，不影响分析结果", extra={"error": str(save_err)})

        logger.info("主力行为分析完成", extra={
            "stock_code": stock_code,
            "time_range": time_range,
            "primary_type": result.get("classification", {}).get("primary_type"),
            "signals_count": len(result.get("signals", [])),
        })

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("主力行为分析失败", extra={
            "stock_code": stock_code,
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.get("/analysis/{stock_code}")
async def get_stock_analysis(stock_code: str, time_range: str = "today"):
    """
    获取指定股票的主力行为分析结果

    路径参数:
        stock_code: 股票代码，如 "000001.SZ"

    查询参数:
        time_range: 时间范围，可选值: today / yesterday / last_5_days

    返回:
        完整的主力行为分析结果
    """
    stock_code = stock_code.strip()
    if not stock_code:
        raise HTTPException(status_code=400, detail="stock_code is required")

    if time_range not in TIME_RANGE_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"time_range must be one of {list(TIME_RANGE_PRESETS.keys())}",
        )

    logger.info("获取主力行为分析结果", extra={
        "stock_code": stock_code,
        "time_range": time_range,
    })

    try:
        engine = MainForceEngine()
        result = engine.analyze_stock(stock_code, time_range=time_range)

        logger.info("主力行为分析结果返回", extra={
            "stock_code": stock_code,
            "time_range": time_range,
            "primary_type": result.get("classification", {}).get("primary_type"),
        })

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取主力行为分析失败", extra={
            "stock_code": stock_code,
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
