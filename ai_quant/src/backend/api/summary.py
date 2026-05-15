"""
数据汇总API模块
提供市场数据汇总查询接口，返回各类市场指标和统计信息
"""

from fastapi import APIRouter

from src.backend..data import get_summary
from src.backend..infra.storage.logging_service import get_logger

logger = get_logger("dashboard")

router = APIRouter(prefix="/api/v1", tags=["summary"])


@router.get("/summary")
def summary() -> dict[str, dict[str, object]]:
    """
    获取市场数据汇总信息

    调用Charles服务获取各类市场数据的汇总统计，包括股票行情、财务数据等

    Returns:
        dict: 包含市场汇总数据的字典
    """
    logger.info("首页数据汇总查询", extra={})
    result = get_summary()
    logger.info("首页数据汇总完成", extra={
        "keys_count": len(result)
    })
    return result
