"""
指数日线数据采集任务

职责：
  定时采集沪深交易所主要指数的日线行情数据，写入 trade_index_daily 表。
  支持增量更新（只采最新数据）和全量刷新两种模式。

数据来源链（按优先级）：
  AKShare（主）> QMT Gateway（备1）> TuShare（备2）

调度建议：
  每个交易日收盘后执行一次（如 16:00 后），cron: "0 16 * * 1-5"
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from core.data.index_data import (
    INDEX_META,
    fetch_index_data,
    list_all_index_codes,
    save_index_data,
    validate_index_data,
)
from core.jobs.common import JobStats
from core.jobs.domains.stock_daily import _log
from infra.storage.logging_service import get_logger

logger = get_logger("job_index_daily")

# 默认回看天数（增量模式下采集最近多少天的数据）
_DEFAULT_LOOKBACK_DAYS = 365
# 全量模式下采集的历史天数
_FULL_LOOKBACK_DAYS = 365 * 5


def run_index_daily(
    cfg: Any,
    mode: str | None,
    params: dict[str, Any] | None,
    progress_callback=None,
) -> JobStats:
    """
    执行指数日线数据采集

    Args:
        cfg: 数据库配置（由 runner 传入）
        mode: 运行模式
            - "full": 全量采集，采集最近 5 年所有指数的数据
            - "incremental": 增量采集（默认），只补最近 1 年的数据
        params: 可选参数
            - index_codes: 指定要采集的指数代码列表（默认采集所有）
        progress_callback: 进度回调

    Returns:
        JobStats: 采集统计结果
    """
    _log("指数日线数据采集任务开始")

    mode = (mode or "incremental").strip().lower()
    now = datetime.now()

    # 确定时间范围
    if mode == "full":
        lookback_days = _FULL_LOOKBACK_DAYS
    else:
        lookback_days = _DEFAULT_LOOKBACK_DAYS

    start_date = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    _log(f"采集模式: {mode}, 时间范围: {start_date} ~ {end_date}")

    # 确定要采集的指数列表
    codes_to_fetch = list_all_index_codes()

    # 如果 params 中指定了特定指数，则覆盖
    if params and "index_codes" in params:
        specified = params["index_codes"]
        if isinstance(specified, list):
            codes_to_fetch = [c for c in specified if c in INDEX_META]
        elif isinstance(specified, str):
            codes_to_fetch = [c.strip() for c in specified.split(",") if c.strip() in INDEX_META]

    _log(f"待采集指数数量: {len(codes_to_fetch)}")
    if not codes_to_fetch:
        _log("无待采集的指数代码，任务结束")
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="unknown",
            fallback_chain=[],
            message="无待采集的指数代码",
        )

    total_processed = 0
    total_written = 0
    failed_codes: list[str] = []
    used_sources: set[str] = set()

    for idx, code in enumerate(codes_to_fetch):
        index_name = INDEX_META.get(code, code)
        _log(f"[{idx + 1}/{len(codes_to_fetch)}] 采集 {code} ({index_name})...")

        try:
            result = fetch_index_data(code, start_date, end_date)
            total_processed += 1

            if result.success:
                used_sources.add(result.data_source)

                # 获取原始数据（通过对应的 fetcher 重新获取）
                from core.data.index_data import _FETCH_CHAIN

                raw_df = None
                for source_name, fetcher in _FETCH_CHAIN:
                    if source_name == result.data_source:
                        raw_df = fetcher(code, start_date, end_date)
                        break

                if raw_df is not None and not raw_df.empty:
                    validated = validate_index_data(raw_df, code)
                    written = save_index_data(validated, code, result.data_source)
                    total_written += written
                    _log(f"  -> 成功: 获取 {result.rows_count} 条, 写入 {written} 条 (来源: {result.data_source})")
                else:
                    _log(f"  -> 警告: 获取成功但无原始数据 (来源: {result.data_source})")
            else:
                failed_codes.append(code)
                _log(f"  -> 失败: {result.error_message} (已尝试: {', '.join(result.fallback_chain or [])})")

        except Exception as e:
            failed_codes.append(code)
            _log(f"  -> 异常: {type(e).__name__}: {str(e)}")

        if progress_callback:
            progress_callback(idx + 1)

    # 汇总
    final_source = "akshare"
    fallback_chain = ["akshare", "qmt", "tushare"]

    _log("=" * 50)
    _log(f"指数日线数据采集完成")
    _log(f"  处理指数: {total_processed}")
    _log(f"  写入条数: {total_written}")
    _log(f"  失败数量: {len(failed_codes)}")
    if failed_codes:
        _log(f"  失败列表: {', '.join(failed_codes)}")
    if used_sources:
        final_source = list(used_sources)[-1]
        _log(f"  使用数据源: {', '.join(used_sources)}")
    _log("=" * 50)

    return JobStats(
        items_processed=total_processed,
        rows_written=total_written,
        failed_items=failed_codes,
        data_source_final=final_source,
        fallback_chain=fallback_chain,
        message=f"指数日线采集完成: {total_written} 条, {len(failed_codes)} 个失败",
    )
