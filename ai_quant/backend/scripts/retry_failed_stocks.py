"""
失败股票重试验证脚本

对指定 runId 中所有失败股票执行定向重采，验证修复效果。
与首次运行进行对比分析，输出重试成功率统计。

用法:
  cd /Users/apple/Desktop/ai_huahua/ai_quant
  source venv/bin/activate
  python3 backend/scripts/retry_failed_stocks.py <run_id>

示例:
  python3 backend/scripts/retry_failed_stocks.py 8b0c66709c6146db950e1fac64414d42
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保能找到项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.db import load_mysql_config, connect, query_dict
from core.jobs.domains.stock_daily import (
    _fetch_qmt,
    _fetch_tushare,
    _fetch_akshare,
    _log,
    set_run_id,
)


def load_failed_items(run_id: str) -> list[str]:
    """从任务运行记录文件中读取失败股票列表"""
    # 搜索 job_runs 目录
    candidates = [
        Path(os.path.dirname(__file__)) / ".." / ".ai_quant" / "job_runs" / f"{run_id}.json",
        Path(os.path.dirname(__file__)) / ".." / ".." / ".ai_quant" / "job_runs" / f"{run_id}.json",
        Path.home() / ".ai_quant" / "job_runs" / f"{run_id}.json",
    ]
    for p in candidates:
        p = p.resolve()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            failed = data.get("failedItems", [])
            total = data.get("itemsProcessed", 0)
            print(f"[RETRY] 读取任务记录: {p}")
            print(f"[RETRY] 任务状态: {data.get('status')}, 处理: {total}, 失败: {len(failed)}")
            return failed
    raise FileNotFoundError(f"未找到 runId={run_id} 的任务记录文件")


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else "8b0c66709c6146db950e1fac64414d42"

    # 设置日志 runId
    set_run_id(run_id)

    print("=" * 70)
    print(f"失败股票重试验证 - runId: {run_id}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 读取失败股票列表
    failed_stocks = load_failed_items(run_id)
    total = len(failed_stocks)
    print(f"\n待重试股票数量: {total}")

    if total == 0:
        print("没有失败股票，无需重试")
        return

    # 展示失败股票分布
    pref_counts: dict[str, int] = {}
    for code in failed_stocks:
        prefix = code.split(".")[0][:3] + "." + code.split(".")[1]
        pref_counts[prefix] = pref_counts.get(prefix, 0) + 1
    print("\n失败股票分布:")
    for prefix, count in sorted(pref_counts.items(), key=lambda x: -x[1]):
        print(f"  {prefix}: {count}")

    # 逐只股票重试验证
    print(f"\n{'='*70}")
    print("开始逐只股票重试验证...")
    print(f"{'='*70}")

    retry_success = 0
    retry_failed = 0
    retry_skipped = 0
    source_stats: dict[str, int] = {}
    results: list[dict] = []

    for idx, code in enumerate(failed_stocks, 1):
        print(f"\n--- [{idx}/{total}] 重试 {code} ---")
        start = datetime.now().strftime("%Y%m%d")

        # 三级容灾重试: QMT -> TuShare -> AkShare
        df = None
        source = "unknown"
        for fetch_fn, src_name in [
            (_fetch_qmt, "qmt"),
            (_fetch_tushare, "tushare"),
            (_fetch_akshare, "akshare"),
        ]:
            df = fetch_fn(code, "20230101", "")
            if df is not None and len(df) > 0:
                source = src_name
                break
            print(f"  [FALLBACK] {code}: {src_name} 失败，尝试下一级...")

        if df is not None and len(df) > 0:
            retry_success += 1
            source_stats[source] = source_stats.get(source, 0) + 1
            print(f"  [成功] 数据源={source}, 行数={len(df)}, 范围={df['date'].min().date()}~{df['date'].max().date()}")
            results.append({"code": code, "success": True, "source": source, "rows": len(df)})
        else:
            retry_failed += 1
            print(f"  [失败] 所有数据源均无法获取数据")
            results.append({"code": code, "success": False, "source": None, "rows": 0})

        # 每批股票间短暂停顿，避免触发限流
        if idx % 10 == 0 and idx < total:
            time.sleep(1.0)

    # 输出总结
    print(f"\n{'='*70}")
    print("重试验证总结")
    print(f"{'='*70}")
    print(f"总重试数: {total}")
    print(f"重试成功: {retry_success} ({retry_success/total*100:.1f}%)")
    print(f"重试失败: {retry_failed} ({retry_failed/total*100:.1f}%)")
    print(f"数据源分布: {source_stats}")
    if retry_failed > 0:
        failed_names = [r["code"] for r in results if not r["success"]]
        print(f"仍失败列表 ({len(failed_names)}): {', '.join(failed_names[:20])}{'...' if len(failed_names) > 20 else ''}")

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 返回退出码: 0=全部成功, 1=部分失败
    sys.exit(0 if retry_failed == 0 else 1)


if __name__ == "__main__":
    main()
