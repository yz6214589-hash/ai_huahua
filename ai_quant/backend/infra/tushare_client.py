"""
TuShare Pro API 客户端

封装 TuShare Pro 接口初始化，提供统一的 pro_api 实例。
所有模块需通过 get_pro_api() 获取已初始化的 pro 实例，
避免重复配置 token 和自定义服务地址。
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("tushare_client")

_TUSHARE_TOKEN = os.getenv("AI_QUANT_TUSHARE_TOKEN") or "9b10f24a59e5ca6a9bea43cbb8d141db0ba4483e21f307ea22cd5457"
_TUSHARE_API_URL = "http://a.sszhixia.cn/"

_pro_instance: Any = None


def get_pro_api():
    """获取 TuShare Pro API 实例（单例模式）

    首次调用时初始化 pro_api，配置自定义 token 和服务地址。
    后续调用直接返回已创建的实例。

    Returns:
        tushare.pro_api 实例，可直接调用 daily()、pro_bar() 等接口
    """
    global _pro_instance
    if _pro_instance is not None:
        return _pro_instance

    try:
        import tushare as ts

        pro = ts.pro_api(_TUSHARE_TOKEN)
        pro._DataApi__http_url = _TUSHARE_API_URL
        _pro_instance = pro
        logger.info("TuShare Pro API 初始化成功 (url=%s)", _TUSHARE_API_URL)
        return _pro_instance
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        # 检测 token 过期错误
        if "token" in error_msg.lower() and ("expired" in error_msg.lower() or "invalid" in error_msg.lower()):
            logger.error(
                "TuShare Pro API token 已过期，请在环境变量 AI_QUANT_TUSHARE_TOKEN 中设置有效的 token"
            )
        else:
            logger.error("TuShare Pro API 初始化失败: %s", error_msg)
        raise


def reset_pro_api():
    """重置 TuShare Pro API 实例（用于测试或重新初始化）"""
    global _pro_instance
    _pro_instance = None


def fetch_daily(ts_code: str, start_date: str = "", end_date: str = "") -> list[dict]:
    """获取股票日线行情数据

    Args:
        ts_code: TuShare 格式股票代码，如 "600519.SH"
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD

    Returns:
        list[dict]: 日线数据列表，每条包含 trade_date/close/vol 等字段
    """
    pro = get_pro_api()
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return []
    return df.to_dict("records")


def fetch_pro_bar(ts_code: str, start_date: str = "", end_date: str = "", limit: int | None = None) -> list[dict]:
    """通过 pro_bar 获取股票日线行情（含复权处理）

    Args:
        ts_code: TuShare 格式股票代码，如 "000001.SZ"
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        limit: 返回数据条数限制

    Returns:
        list[dict]: 日线数据列表
    """
    import tushare as ts

    pro = get_pro_api()
    kwargs: dict[str, Any] = {
        "api": pro,
        "ts_code": ts_code,
    }
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    if limit is not None:
        kwargs["limit"] = limit

    df = ts.pro_bar(**kwargs)
    if df is None or df.empty:
        return []
    return df.to_dict("records")
